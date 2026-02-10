"""Core library for extracting genomic metadata from IGO LIMS REST API.

Provides wrapper classes for LIMS JSON responses and API functions for
fetching request samples, sample manifests, and deliveries.
"""

import os
import re
import sys

import requests
import urllib3

urllib3.disable_warnings()

try:
    from conf import settings
except ImportError:
    print("\n\tNeed to setup the conf.py module with credentials\n")
    sys.exit()

LIMS_AUTH = (settings.LIMS_USERNAME, settings.LIMS_PASSWORD)


def get_zone_from_env() -> str:
    """Detect compute zone from CDC_JOINED_ZONE environment variable.

    Returns:
        Zone name string (e.g., "IRIS_01", "JUNO_01"), or "_UNKNOWN_ZONE"
        if the environment variable is unset or unparseable.
    """
    cdc_joined_zone = os.environ.get("CDC_JOINED_ZONE")
    if cdc_joined_zone is None:
        return "_UNKNOWN_ZONE"

    match = re.search(r"CN=([^,]+),", cdc_joined_zone)
    if match:
        return match.group(1)
    return "_UNKNOWN_ZONE"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ETLException(Exception):
    """Base exception for ETL errors."""

    code = None


class LIMSRequestException(ETLException):
    """Failed to get response from LIMS or data not in expected format."""

    code = 101


# ---------------------------------------------------------------------------
# LIMS JSON wrapper classes
#
# These classes assign __dict__ directly from the API JSON response,
# so their attributes mirror the LIMS field names (camelCase).
# ---------------------------------------------------------------------------


class Sample:
    """Single sample from a LIMS request.

    Attributes from JSON: investigatorSampleId, igoSampleId, igoComplete.
    """

    def __init__(self, sample_json: dict) -> None:
        self.__dict__ = sample_json
        self.json = sample_json

    def __str__(self) -> str:
        try:
            return (
                f"<limsETL.Sample {self.investigatorSampleId} "
                f"{self.igoSampleId} {self.igoComplete}>"
            )
        except AttributeError:
            print(f"\n\n{self.json}\n\n")
            raise


class RequestSamples:
    """Collection of samples for a LIMS request.

    Attributes from JSON: requestId, recipe, samples, investigatorName,
    labHeadName, piEmail, dataAnalystName, projectManagerName, strand,
    pooledNormals, and various email fields.
    """

    def __init__(self, req_samples_json: dict) -> None:
        self.__dict__ = req_samples_json
        self.samples = [Sample(x) for x in self.samples]


def _get_run_id(fastq_path: str) -> str:
    """Extract run ID from a FASTQ file path.

    Parses the path component two levels below '/FASTQ/'.

    Args:
        fastq_path: Full path to a FASTQ file.

    Returns:
        Run ID string.
    """
    pos = fastq_path.find("/FASTQ/")
    return fastq_path[pos:].split("/")[2]


class MachineRun:
    """A single sequencing machine run derived from a FASTQ path.

    Attributes:
        fastqDir: Directory containing FASTQ files.
        runId: Sequencing run identifier.
        runType: "SE" (single-end) or "PE" (paired-end).
    """

    def __init__(self, fastq_path: str) -> None:
        self.fastqDir = os.path.dirname(fastq_path)
        self.runId = _get_run_id(fastq_path)
        self.runType = "SE"


class Run:
    """Sequencing run containing FASTQ files grouped by machine run.

    Attributes from JSON: fastqs, flowCellId, flowCellLanes, readLength,
    runDate, runId, runMode.

    Attributes derived: machineRuns (dict of run_id -> MachineRun, or None).
    """

    def __init__(self, run_json: dict) -> None:
        self.__dict__ = run_json

        if not self.fastqs:
            self.machineRuns = None
            return

        machine_runs: dict[str, MachineRun] = {}
        for fastq_path in self.fastqs:
            run_id = _get_run_id(fastq_path)
            if run_id not in machine_runs:
                machine_runs[run_id] = MachineRun(fastq_path)
            if "_R2_" in fastq_path:
                machine_runs[run_id].runType = "PE"

        self.machineRuns = machine_runs


class Library:
    """Sequencing library with associated runs.

    Attributes from JSON: barcodeId, barcodeIndex, captureConcentrationNm,
    captureInputNg, captureName, dnaInputNg, libraryConcentrationNgul,
    libraryIgoId, libraryVolume, runs.
    """

    def __init__(self, library_json: dict) -> None:
        self.__dict__ = library_json
        self.runs = [Run(x) for x in self.runs]


class SampleManifest:
    """Full sample manifest with metadata and library information.

    Attributes from JSON: baitSet, cmoPatientId, cmoSampleClass,
    cmoSampleName, collectionYear, igoId, investigatorSampleId,
    libraries, oncoTreeCode, preservation, sampleName, sampleOrigin,
    sex, species, specimenType, tissueLocation, tumorOrNormal.
    """

    def __init__(self, sample_metadata_json: dict) -> None:
        self.__dict__ = sample_metadata_json
        self.libraries = [Library(x) for x in self.libraries]


# ---------------------------------------------------------------------------
# LIMS API functions
# ---------------------------------------------------------------------------


def get_deliveries(timestamp: str) -> list:
    """Fetch recent deliveries from LIMS.

    Args:
        timestamp: Cutoff timestamp for delivery query.

    Returns:
        List of delivery records, or empty list if none found.

    Raises:
        LIMSRequestException: If the API request fails.
    """
    response = requests.get(
        f"{settings.LIMS_ROOT_URL}/getDeliveries",
        params={"timestamp": timestamp},
        auth=LIMS_AUTH,
        verify=False,
    )
    if response.status_code != 200:
        raise LIMSRequestException("Failed to fetch new requests")
    if not response.json():
        print("There are no new RequestIDs")
        return []
    return response.json()


def get_request_samples(request_id: str) -> RequestSamples:
    """Fetch all samples for a LIMS request.

    Args:
        request_id: IGO request/project ID.

    Returns:
        RequestSamples object containing sample data.

    Raises:
        LIMSRequestException: If the API request fails or returns
            mismatched request ID.
    """
    response = requests.get(
        f"{settings.LIMS_ROOT_URL}/getRequestSamples",
        params={"request": request_id},
        auth=LIMS_AUTH,
        verify=False,
    )
    if response.status_code != 200:
        raise LIMSRequestException(f"Failed to fetch request_id {request_id}")
    data = response.json()
    if data["requestId"] != request_id:
        raise LIMSRequestException(
            f"Invalid LIMS record requestId!=request_id "
            f"[{data['requestId']},{request_id}]"
        )
    return RequestSamples(data)


def get_sample_manifest(sample_id: str) -> SampleManifest:
    """Fetch sample manifest metadata from LIMS.

    Args:
        sample_id: IGO sample ID.

    Returns:
        SampleManifest object with full sample metadata.

    Raises:
        LIMSRequestException: If the API request fails, returns invalid
            data, or returns a mismatched sample ID.
    """
    response = requests.get(
        f"{settings.LIMS_ROOT_URL}/getSampleManifest",
        params={"igoSampleId": sample_id},
        auth=LIMS_AUTH,
        verify=False,
    )
    if response.status_code != 200:
        raise LIMSRequestException(
            f"Failed to fetch SampleManifest for sampleId:{sample_id}"
        )
    try:
        data = response.json()[0]
    except Exception:
        raise LIMSRequestException(
            f"Failed to fetch SampleManifest for sampleId:{sample_id}. "
            "Invalid response"
        )
    if data["igoId"] != sample_id:
        raise LIMSRequestException(
            f"Failed to fetch SampleManifest for sampleId:{sample_id}. "
            f"LIMS returned {data['igoId']}"
        )
    return SampleManifest(data)


# Backward-compatible aliases for the renamed API functions
getDeliveries = get_deliveries
getRequestSamples = get_request_samples
getSampleManifest = get_sample_manifest
