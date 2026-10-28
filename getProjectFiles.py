#!/usr/bin/env python3
"""Extract project metadata from IGO LIMS and generate standardized project files."""

import argparse
import csv
import json
import os
import re
import sys

import limsDB
import limsETL

# FASTQ folder roots by compute zone
JUNO_ROOT = "/igo/delivery/FASTQ/"
IRIS_ROOT = "/data1/test01/bic/CACHE/ifs/datadelivery/igo_core/FASTQ/"

SAMPLE_FIELDS = [
    "investigatorSampleId",
    "sampleName",
    "cmoPatientId",
    "igoId",
    "baitSet",
    "cmoSampleClass",
    "tumorOrNormal",
    "preservation",
    "sampleOrigin",
    "specimenType",
    "oncoTreeCode",
    "tissueLocation",
    "collectionYear",
    "sex",
    "species",
]

MISSING_SAMPLE_MESSAGE = """
No FASTQ files for:
            igoId: {igo_id}
       sampleName: {sample_name}
   investSampleId: {invest_sample_id}
"""


def pull_request(project_no: str) -> str:
    """Pull a request from LIMS as JSON text.

    Args:
        project_no: IGO project number.

    Returns:
        Request JSON text.

    Raises:
        limsETL.LIMSRequestException: If LIMS returns an error.
    """
    print(f"\nPulling request {project_no} from LIMS")
    return json.dumps(limsETL.get_request_samples_json(project_no))


def pull_sample_manifest(sample_id: str) -> str | None:
    """Pull a sample manifest from LIMS as JSON text.

    The manifest is parsed once as a check, so a malformed record
    counts as a failed pull and is not stored.

    Args:
        sample_id: IGO sample ID.

    Returns:
        Manifest JSON text, or None if the pull failed.
    """
    print(f"Pulling sample {sample_id} ...", end="")
    try:
        manifest_json = json.dumps(limsETL.get_sample_manifest_json(sample_id))
        limsETL.SampleManifest(json.loads(manifest_json))
    except Exception as exc:
        print(f"\n   Failed to pull sample {sample_id}: {exc}\n")
        return None

    print(" done")
    return manifest_json


def collect_manifests(
    primary: list[limsETL.Sample],
    stored_manifests: dict[str, str],
    is_local: bool,
) -> tuple[list[limsETL.SampleManifest], list[limsETL.Sample], dict[str, str]]:
    """Get a manifest for each primary sample, from storage or LIMS.

    Samples in stored_manifests are read from it. Others are pulled
    from LIMS, except that when working from a local copy only
    complete samples are pulled again; incomplete samples missing from
    the local copy count as failed.

    Args:
        primary: Request samples with primary IGO IDs.
        stored_manifests: Dict mapping IGO ID to stored manifest JSON.
        is_local: True when the request came from the local database.

    Returns:
        Tuple of (manifests in request order, request samples with no
        manifest, dict of newly pulled manifest JSON by IGO ID).
    """
    samples = []
    failed_fetch = []
    new_manifests = {}
    for sample_info in primary:
        igo_id = sample_info.igoSampleId
        manifest_json = stored_manifests.get(igo_id)
        if manifest_json is None and (not is_local or sample_info.igoComplete):
            manifest_json = pull_sample_manifest(igo_id)
            if manifest_json is not None:
                new_manifests[igo_id] = manifest_json
        if manifest_json is None:
            failed_fetch.append(sample_info)
        else:
            samples.append(limsETL.SampleManifest(json.loads(manifest_json)))

    return samples, failed_fetch, new_manifests


def get_sample_mapping_data(
    sample_obj: limsETL.SampleManifest,
) -> list[list]:
    """Extract run ID, FASTQ directory, and run type for each machine run.

    Args:
        sample_obj: SampleManifest with library and run information.

    Returns:
        List of [run_id, fastq_dir, run_type] entries.
    """
    mapping_data = []
    for lib in sample_obj.libraries:
        for run in lib.runs:
            if run.machineRuns is not None:
                for run_id, machine_run in run.machineRuns.items():
                    mapping_data.append(
                        [run_id, machine_run.fastqDir, machine_run.runType]
                    )
            else:
                print(
                    MISSING_SAMPLE_MESSAGE.format(
                        igo_id=sample_obj.igoId,
                        sample_name=sample_obj.sampleName,
                        invest_sample_id=sample_obj.investigatorSampleId,
                    )
                )

    return mapping_data


def derive_sample_id_from_fastq(fastq_dir: str) -> str:
    """Derive investigatorSampleId from FASTQ directory path.

    Strips 'Sample_' prefix and '_IGO_' suffix from the directory basename.

    Args:
        fastq_dir: Path to FASTQ directory.

    Returns:
        Derived sample ID string.
    """
    sample_id = os.path.basename(fastq_dir).replace("Sample_", "")
    pos = sample_id.find("_IGO_")
    if pos >= 0:
        sample_id = sample_id[:pos]
    return sample_id


def fallback_sample_id(
    sample: limsETL.SampleManifest,
    sample_map_data: list[list],
) -> str:
    """Pick a sample ID when LIMS has no investigatorSampleId.

    Tries, in order: the ID derived from the first FASTQ directory,
    sampleName, cmoSampleName, and finally igoId.

    Args:
        sample: SampleManifest with a null investigatorSampleId.
        sample_map_data: List of [run_id, fastq_dir, run_type] entries.

    Returns:
        Sample ID string.
    """
    if sample_map_data:
        return derive_sample_id_from_fastq(sample_map_data[0][1])
    for field in ("sampleName", "cmoSampleName"):
        value = getattr(sample, field, None)
        if value:
            return value
    return sample.igoId


def write_mapping_file(
    mapping_path: str,
    samples: list[limsETL.SampleManifest],
    sample_request_db: dict,
    zone: str,
) -> tuple[set[str], list[limsETL.SampleManifest]]:
    """Write sample-to-FASTQ mapping file and collect bait sets.

    Completed samples with no FASTQ files in LIMS are left out of the
    mapping file and returned to the caller.

    Args:
        mapping_path: Output file path for mapping TSV.
        samples: List of SampleManifest objects.
        sample_request_db: Dict mapping IGO ID to Sample request objects.
        zone: Compute zone string (e.g., "IRIS_01", "JUNO_01").

    Returns:
        Tuple of (set of bait set names used across completed samples,
        list of completed samples with no FASTQ files).
    """
    baits_used = set()
    missing_fastq = []

    with open(mapping_path, "w") as fp:
        print("SampleId,IGOId,CompleteFlag")
        for sample in samples:
            request_info = sample_request_db[sample.igoId]
            summary = [
                sample.investigatorSampleId,
                sample.igoId,
                request_info.igoComplete,
            ]
            print(",".join(map(str, summary)))

            if not request_info.igoComplete:
                continue

            if sample.baitSet is not None:
                baits_used.add(sample.baitSet)

            sample_map_data = get_sample_mapping_data(sample)

            if sample.investigatorSampleId is None:
                sample.investigatorSampleId = fallback_sample_id(
                    sample, sample_map_data
                )

            if not sample_map_data:
                missing_fastq.append(sample)
                continue

            prefix = ["_1", sample.investigatorSampleId]
            for run_id, fastq_dir, run_type in sample_map_data:
                if run_id == "":
                    continue
                if zone.startswith("IRIS"):
                    fastq_dir = fastq_dir.replace(JUNO_ROOT, IRIS_ROOT)
                row = prefix + [run_id, fastq_dir, run_type]
                fp.write("\t".join(map(str, row)) + "\n")

    return baits_used, missing_fastq


def write_request_file(
    request_path: str,
    request_data: limsETL.RequestSamples,
) -> None:
    """Write request-level metadata as YAML.

    Args:
        request_path: Output file path.
        request_data: RequestSamples object with project metadata.
    """
    fields_to_ignore = {"samples", "pooledNormals"}
    with open(request_path, "w") as fp:
        for field in request_data.__dict__:
            if field not in fields_to_ignore:
                fp.write(f'{field}: "{getattr(request_data, field)}"\n')


def write_manifest_file(
    manifest_path: str,
    samples: list[limsETL.SampleManifest],
    sample_request_db: dict,
) -> None:
    """Write sample metadata CSV file.

    Values that contain commas, quotes, or newlines are quoted, so a
    field such as "Lung, left" stays in its own column.

    Args:
        manifest_path: Output file path.
        samples: List of SampleManifest objects.
        sample_request_db: Dict mapping IGO ID to Sample request objects.
    """
    header = SAMPLE_FIELDS + ["IGOComplete"]
    with open(manifest_path, "w", newline="") as fp:
        writer = csv.writer(fp, lineterminator="\n")
        writer.writerow(header)
        for sample in samples:
            row = [str(sample.__dict__[field]) for field in SAMPLE_FIELDS]
            row.append(str(sample_request_db[sample.igoId].igoComplete))
            writer.writerow(row)


PROJ_DIR_PATTERN = re.compile(r".*/Proj_([^/]+)/")


def project_no_from_cwd() -> str:
    """Extract project number from current working directory.

    Matches the pattern .*/Proj_<ID>/ in the cwd path.

    Returns:
        Project number string.

    Raises:
        SystemExit: If cwd does not match the expected pattern.
    """
    match = PROJ_DIR_PATTERN.match(os.getcwd() + "/")
    if not match:
        print(f"Error: could not extract project number from cwd: {os.getcwd()}")
        print("Expected path containing Proj_<ID>/ directory")
        sys.exit(1)
    return match.group(1)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace with project_no and force attributes.
    """
    parser = argparse.ArgumentParser(
        description="Extract project metadata from IGO LIMS and generate "
        "standardized project files for BIC analysis pipelines. "
        "Pulled data is stored in a local SQLite database and reused on "
        "later runs.",
        epilog="Output files: Proj_<ID>_metadata.yaml, "
        "Proj_<ID>_sample_mapping.txt, Proj_<ID>_metadata_samples.csv",
    )
    parser.add_argument(
        "project_no",
        metavar="PROJECT_NUMBER",
        nargs="?",
        help="IGO project number (e.g., 12345)",
    )
    parser.add_argument(
        "-d",
        action="store_true",
        help="derive project number from current working directory "
        "(expects Proj_<ID>/ in path)",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="pull the request from LIMS even if a local copy exists, "
        "and replace the local copy",
    )
    args = parser.parse_args(argv)

    if args.d and args.project_no:
        parser.error("-d and PROJECT_NUMBER are mutually exclusive")
    if args.d:
        args.project_no = project_no_from_cwd()
    if not args.project_no:
        parser.error("PROJECT_NUMBER is required (or use -d)")

    return args


def main() -> None:
    """Main entry point: extract LIMS data and generate project files."""
    args = parse_args()

    zone = limsETL.get_zone_from_env()
    print(f"{zone=}")

    project_no = args.project_no
    print(f"\n{project_no=}")

    igo_id_pattern = re.compile(rf"^{project_no}_\d+$")

    db_path = limsDB.get_db_path()
    conn = limsDB.connect(db_path)

    # Use the local copy of the request unless -f was given
    stored = None if args.force else limsDB.get_request(conn, project_no)
    if stored is None:
        request_json = pull_request(project_no)
        pulled_at = limsDB.timestamp()
        stored_manifests = {}
    else:
        request_json, pulled_at = stored
        stored_manifests = limsDB.get_sample_manifests(conn, project_no)
        print(
            f"\nRetrieving local copy of request {project_no} pulled on "
            f"{limsDB.format_timestamp(pulled_at)}"
        )
    is_local = stored is not None

    request_data = limsETL.RequestSamples(json.loads(request_json))
    sample_request_db = {x.igoSampleId: x for x in request_data.samples}

    # Use primary IGO IDs only
    primary = []
    for sample_info in request_data.samples:
        if igo_id_pattern.match(sample_info.igoSampleId):
            primary.append(sample_info)
        else:
            print(f"\nInvalid igoId={sample_info.igoSampleId}")

    if is_local:
        retry = [
            s
            for s in primary
            if s.igoComplete and s.igoSampleId not in stored_manifests
        ]
        if retry:
            print(
                f"\nLocal copy is missing {len(retry)} complete sample(s); "
                "pulling them from LIMS"
            )

    samples, failed_fetch, new_manifests = collect_manifests(
        primary, stored_manifests, is_local
    )

    if is_local:
        if new_manifests:
            limsDB.save_sample_manifests(
                conn, project_no, limsDB.timestamp(), new_manifests
            )
    else:
        limsDB.save_request(conn, project_no, request_json, pulled_at, new_manifests)
        print(f"\nSaved request {project_no} to {db_path}")
    conn.close()

    if not samples:
        print(
            f"\nNo sample manifests available for request {project_no}\n",
            file=sys.stderr,
        )
        sys.exit(1)

    print()

    # Output file paths
    request_file = f"Proj_{project_no}_metadata.yaml"
    mapping_file = f"Proj_{project_no}_sample_mapping.txt"
    manifest_file = f"Proj_{project_no}_metadata_samples.csv"

    # Aggregate species across samples
    species = ",".join({s.species for s in samples if s.species is not None})
    request_data.Species = species
    # Count every primary IGO ID, including failed fetches
    request_data.NumberOfSamples = len(samples) + len(failed_fetch)

    # Write mapping file and collect bait sets
    baits_used, missing_fastq = write_mapping_file(
        mapping_file, samples, sample_request_db, zone
    )
    request_data.baitsUsed = ";".join(str(b) for b in baits_used)
    print(f"\nBaitsUsed = {request_data.baitsUsed}")

    # Write metadata and manifest files
    write_request_file(request_file, request_data)
    write_manifest_file(manifest_file, samples, sample_request_db)

    if is_local:
        incomplete = [s for s in primary if not s.igoComplete]
        if incomplete:
            print(
                f"\nWARNING: {len(incomplete)} sample(s) were incomplete when "
                f"pulled on {limsDB.format_timestamp(pulled_at)}; "
                "use -f to refresh",
                file=sys.stderr,
            )

    failed_complete = [s for s in failed_fetch if s.igoComplete]
    if failed_complete:
        print(
            f"\nERROR: {len(failed_complete)} complete sample(s) could not "
            "be pulled from LIMS; left out of all output files:",
            file=sys.stderr,
        )
        for sample_info in failed_complete:
            invest_id = getattr(sample_info, "investigatorSampleId", None)
            print(
                f"   {sample_info.igoSampleId}\t{invest_id}",
                file=sys.stderr,
            )

    if missing_fastq:
        print(
            f"\nERROR: {len(missing_fastq)} complete sample(s) have no "
            f"FASTQ files in LIMS; left out of {mapping_file}:",
            file=sys.stderr,
        )
        for sample in missing_fastq:
            print(
                f"   {sample.igoId}\t{sample.investigatorSampleId}",
                file=sys.stderr,
            )

    if failed_complete or missing_fastq:
        sys.exit(1)


if __name__ == "__main__":
    main()
