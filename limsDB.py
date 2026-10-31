"""Local SQLite copy of LIMS request and sample manifest data.

Each LIMS response is stored as raw JSON with the time it was pulled.
SQL views (v_requests, v_request_samples, v_samples, v_fastqs) expose
common fields as columns for querying from Python or R.

LIMS writes a missing value in several ways: JSON null, "", "null",
"N/A", "NA", "na". The views return all of them as NULL, and
clean_missing() sets them to None in parsed JSON. The stored JSON is
left as LIMS sent it.

The database uses SQLite's default rollback journal. WAL mode is not
used because it needs shared memory on one host, and the database may
sit on a network filesystem.
"""

import datetime
import os
import sqlite3

try:
    from conf import settings
except ImportError:
    settings = None

DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "limsDB.sqlite"
)

SCHEMA_VERSION = 2

# Text LIMS uses for a missing value, matched after trimming spaces and
# lowercasing. Treated the same as JSON null.
MISSING_TEXT = ("", "null", "none", "na", "n/a")

TABLES_SQL = """
CREATE TABLE IF NOT EXISTS requests (
    request_id TEXT PRIMARY KEY,
    pulled_at  TEXT NOT NULL,
    json       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sample_manifests (
    igo_id     TEXT PRIMARY KEY,
    request_id TEXT NOT NULL
               REFERENCES requests (request_id) ON DELETE CASCADE,
    pulled_at  TEXT NOT NULL,
    json       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS sample_manifests_request_id
    ON sample_manifests (request_id);
"""

REQUEST_FIELDS = [
    "requestName",
    "recipe",
    "libraryType",
    "strand",
    "labHeadName",
    "labHeadEmail",
    "investigatorName",
    "investigatorEmail",
    "projectManagerName",
    "dataAnalystName",
    "isCmoRequest",
    "bicAnalysis",
    "deliveryDate",
    "deliveryPath",
]

MANIFEST_FIELDS = [
    "investigatorSampleId",
    "sampleName",
    "cmoSampleName",
    "cmoPatientId",
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


def _json_column(source: str, field: str) -> str:
    """Build a SELECT column that pulls one field out of JSON.

    Text in MISSING_TEXT is returned as NULL.

    Args:
        source: SQL expression holding the JSON, e.g. "m.json".
        field: Field name, also used as the column name.

    Returns:
        SQL column expression with an AS clause.
    """
    value = f"json_extract({source}, '$.{field}')"
    missing = ", ".join(f"'{text}'" for text in MISSING_TEXT)
    return (
        f"CASE WHEN lower(trim({value})) IN ({missing}) "
        f"THEN NULL ELSE {value} END AS {field}"
    )


def _json_columns(source: str, fields: list[str]) -> str:
    """Build SELECT columns that pull fields out of JSON.

    Args:
        source: SQL expression holding the JSON, e.g. "m.json".
        fields: Field names, also used as the column names.

    Returns:
        Comma-separated SQL column expressions.
    """
    return ",\n    ".join(_json_column(source, field) for field in fields)


VIEWS_SQL = f"""
DROP VIEW IF EXISTS v_requests;
CREATE VIEW v_requests AS
SELECT
    r.request_id,
    r.pulled_at,
    {_json_columns("r.json", REQUEST_FIELDS)},
    json_array_length(r.json, '$.samples') AS numSamples
FROM requests r;

DROP VIEW IF EXISTS v_request_samples;
CREATE VIEW v_request_samples AS
SELECT
    r.request_id,
    json_extract(s.value, '$.igoSampleId') AS igoSampleId,
    {_json_column("s.value", "investigatorSampleId")},
    json_extract(s.value, '$.igoComplete') AS igoComplete
FROM requests r, json_each(r.json, '$.samples') s;

DROP VIEW IF EXISTS v_samples;
CREATE VIEW v_samples AS
SELECT
    m.request_id,
    m.igo_id,
    m.pulled_at,
    {_json_columns("m.json", MANIFEST_FIELDS)},
    rs.igoComplete
FROM sample_manifests m
LEFT JOIN v_request_samples rs
    ON rs.request_id = m.request_id AND rs.igoSampleId = m.igo_id;

DROP VIEW IF EXISTS v_fastqs;
CREATE VIEW v_fastqs AS
SELECT
    m.request_id,
    m.igo_id,
    {_json_column("lib.value", "libraryIgoId")},
    {_json_columns("run.value", ["runId", "flowCellId", "runDate"])},
    fq.value AS fastq
FROM sample_manifests m,
    json_each(m.json, '$.libraries') lib,
    json_each(lib.value, '$.runs') run,
    json_each(run.value, '$.fastqs') fq
WHERE fq.type = 'text';
"""

UPSERT_MANIFEST_SQL = """
INSERT INTO sample_manifests (igo_id, request_id, pulled_at, json)
VALUES (?, ?, ?, ?)
ON CONFLICT (igo_id) DO UPDATE SET
    request_id = excluded.request_id,
    pulled_at = excluded.pulled_at,
    json = excluded.json
"""


def get_db_path() -> str:
    """Return the database path.

    Uses settings.LIMS_DB_PATH from conf.py when it is set, otherwise
    limsDB.sqlite in the code directory.

    Returns:
        Path to the SQLite database file.
    """
    path = getattr(settings, "LIMS_DB_PATH", None) or DEFAULT_DB_PATH
    return os.path.expanduser(path)


def connect(path: str) -> sqlite3.Connection:
    """Open the database, creating tables and views if needed.

    Args:
        path: Path to the SQLite database file.

    Returns:
        Open connection with foreign keys enabled.
    """
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        conn.executescript(
            TABLES_SQL + VIEWS_SQL + f"PRAGMA user_version = {SCHEMA_VERSION};"
        )
    return conn


def timestamp() -> str:
    """Return the current local time as an ISO 8601 string.

    Returns:
        Time with UTC offset, e.g. "2026-10-28T14:03:12-04:00".
    """
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def format_timestamp(stamp: str) -> str:
    """Format a stored timestamp for display in local time.

    Args:
        stamp: ISO 8601 string from timestamp().

    Returns:
        Time as "YYYY-MM-DD HH:MM".
    """
    when = datetime.datetime.fromisoformat(stamp).astimezone()
    return when.strftime("%Y-%m-%d %H:%M")


def clean_missing(record: dict) -> dict:
    """Set LIMS missing-value text in a parsed JSON record to None.

    Uses the same rule as the views: text in MISSING_TEXT, after
    trimming spaces and lowercasing. Only top-level values are
    checked. The dict is changed in place.

    Args:
        record: Dict parsed from LIMS JSON.

    Returns:
        The same dict.
    """
    for key, value in record.items():
        if isinstance(value, str) and value.strip(" ").lower() in MISSING_TEXT:
            record[key] = None
    return record


def get_request(conn: sqlite3.Connection, request_id: str) -> tuple[str, str] | None:
    """Look up a stored request.

    Args:
        conn: Open database connection.
        request_id: IGO request/project ID.

    Returns:
        Tuple of (request JSON text, pulled_at), or None if the request
        is not stored.
    """
    return conn.execute(
        "SELECT json, pulled_at FROM requests WHERE request_id = ?",
        (request_id,),
    ).fetchone()


def get_sample_manifests(conn: sqlite3.Connection, request_id: str) -> dict[str, str]:
    """Return the stored sample manifests for a request.

    Args:
        conn: Open database connection.
        request_id: IGO request/project ID.

    Returns:
        Dict mapping IGO sample ID to manifest JSON text.
    """
    rows = conn.execute(
        "SELECT igo_id, json FROM sample_manifests WHERE request_id = ?",
        (request_id,),
    )
    return dict(rows.fetchall())


def save_request(
    conn: sqlite3.Connection,
    request_id: str,
    request_json: str,
    pulled_at: str,
    manifests: dict[str, str],
) -> None:
    """Store a request and its sample manifests, replacing any earlier copy.

    All stored manifests for the request are deleted first, so samples
    that are no longer in the request, or that failed to pull, do not
    keep old data.

    Args:
        conn: Open database connection.
        request_id: IGO request/project ID.
        request_json: Request JSON text.
        pulled_at: Pull time from timestamp().
        manifests: Dict mapping IGO sample ID to manifest JSON text.
    """
    with conn:
        conn.execute(
            "DELETE FROM sample_manifests WHERE request_id = ?", (request_id,)
        )
        conn.execute(
            "INSERT INTO requests (request_id, pulled_at, json) VALUES (?, ?, ?) "
            "ON CONFLICT (request_id) DO UPDATE SET "
            "pulled_at = excluded.pulled_at, json = excluded.json",
            (request_id, pulled_at, request_json),
        )
        conn.executemany(
            UPSERT_MANIFEST_SQL,
            [(igo_id, request_id, pulled_at, j) for igo_id, j in manifests.items()],
        )


def save_sample_manifests(
    conn: sqlite3.Connection,
    request_id: str,
    pulled_at: str,
    manifests: dict[str, str],
) -> None:
    """Add or replace sample manifests for a stored request.

    The request row and its pull time are left unchanged.

    Args:
        conn: Open database connection.
        request_id: IGO request/project ID (must already be stored).
        pulled_at: Pull time from timestamp().
        manifests: Dict mapping IGO sample ID to manifest JSON text.
    """
    with conn:
        conn.executemany(
            UPSERT_MANIFEST_SQL,
            [(igo_id, request_id, pulled_at, j) for igo_id, j in manifests.items()],
        )
