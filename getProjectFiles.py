#!/usr/bin/env python3
"""Extract project metadata from IGO LIMS and generate standardized project files."""

import argparse
import datetime
import os
import re
import sys

try:
    from cachier import cachier
except ModuleNotFoundError:
    print("No Cachier Module so no cacheing")

    def cachier(*args, **kwargs):
        def inner(f):
            return f

        return inner


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


def get_request_samples(project_no: str) -> limsETL.RequestSamples:
    """Fetch request samples from LIMS for a project.

    Args:
        project_no: IGO project number.

    Returns:
        RequestSamples object with sample data.
    """
    return limsETL.getRequestSamples(project_no)


@cachier(cache_dir="./__cache__", stale_after=datetime.timedelta(days=1))
def get_sample_manifest(sample_id: str) -> limsETL.SampleManifest:
    """Fetch sample manifest from LIMS, creating a null record on failure.

    Args:
        sample_id: IGO sample ID.

    Returns:
        SampleManifest object (may be null record if fetch failed).
    """
    print(f"Pulling sample {sample_id} ...", end="")
    try:
        sample_manifest = limsETL.getSampleManifest(sample_id)
    except Exception:
        print(f"\n   Invalid Sample ID {sample_id}")
        print("   Creating NULL record\n")
        null_sample = dict(
            libraries=[],
            species=".NA",
            investigatorSampleId=".NA",
            igoId=sample_id,
        )
        sample_manifest = limsETL.SampleManifest(null_sample)

    print(" done")
    return sample_manifest


@cachier(cache_dir="./__cache__", stale_after=datetime.timedelta(days=1))
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


def write_mapping_file(
    mapping_path: str,
    samples: list[limsETL.SampleManifest],
    sample_request_db: dict,
    zone: str,
) -> set[str]:
    """Write sample-to-FASTQ mapping file and collect bait sets.

    Args:
        mapping_path: Output file path for mapping TSV.
        samples: List of SampleManifest objects.
        sample_request_db: Dict mapping IGO ID to Sample request objects.
        zone: Compute zone string (e.g., "IRIS_01", "JUNO_01").

    Returns:
        Set of bait set names used across completed samples.
    """
    baits_used = set()

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
                sample.investigatorSampleId = derive_sample_id_from_fastq(
                    sample_map_data[0][1]
                )

            prefix = ["_1", sample.investigatorSampleId]
            for run_id, fastq_dir, run_type in sample_map_data:
                if run_id == "":
                    continue
                if zone.startswith("IRIS"):
                    fastq_dir = fastq_dir.replace(JUNO_ROOT, IRIS_ROOT)
                row = prefix + [run_id, fastq_dir, run_type]
                fp.write("\t".join(map(str, row)) + "\n")

    return baits_used


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

    Args:
        manifest_path: Output file path.
        samples: List of SampleManifest objects.
        sample_request_db: Dict mapping IGO ID to Sample request objects.
    """
    header = SAMPLE_FIELDS + ["IGOComplete"]
    with open(manifest_path, "w") as fp:
        fp.write(",".join(header) + "\n")
        for sample in samples:
            if sample.investigatorSampleId == ".NA":
                continue
            row = [str(sample.__dict__[field]) for field in SAMPLE_FIELDS]
            row.append(str(sample_request_db[sample.igoId].igoComplete))
            fp.write(",".join(row) + "\n")


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
        Parsed namespace with project_no attribute.
    """
    parser = argparse.ArgumentParser(
        description="Extract project metadata from IGO LIMS and generate "
        "standardized project files for BIC analysis pipelines.",
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

    request_data = get_request_samples(project_no)
    sample_request_db = {x.igoSampleId: x for x in request_data.samples}

    # Fetch manifests for primary IGO IDs only
    samples = []
    for sample_info in request_data.samples:
        if igo_id_pattern.match(sample_info.igoSampleId):
            manifest = get_sample_manifest(sample_info.igoSampleId)
            samples.append(manifest)
        else:
            print(f"\nInvalid igoId={sample_info.igoSampleId}")

    samples = [s for s in samples if s is not None]

    if len(samples) < 1:
        print("\nAll samples failed when pulling from LIMS\n")
        sys.exit()

    print()

    # Output file paths
    request_file = f"Proj_{project_no}_metadata.yaml"
    mapping_file = f"Proj_{project_no}_sample_mapping.txt"
    manifest_file = f"Proj_{project_no}_metadata_samples.csv"

    # Aggregate species across samples
    species = ",".join(
        {s.species for s in samples if s.species is not None and s.species != ".NA"}
    )
    request_data.Species = species
    request_data.NumberOfSamples = len(samples)

    # Write mapping file and collect bait sets
    baits_used = write_mapping_file(mapping_file, samples, sample_request_db, zone)
    request_data.baitsUsed = ";".join(str(b) for b in baits_used)
    print(f"\nBaitsUsed = {request_data.baitsUsed}")

    # Write metadata and manifest files
    write_request_file(request_file, request_data)
    write_manifest_file(manifest_file, samples, sample_request_db)


if __name__ == "__main__":
    main()
