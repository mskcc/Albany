# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LimsETL (v2.1.0) extracts genomic project metadata from IGO LIMS via REST API and generates standardized project files for BIC analysis pipelines (variant calling, RNA-seq, ChIP-seq).

## Architecture

### Data Flow

```
IGO LIMS REST API
    |
    v
limsDB.sqlite       (local copy of pulled requests and manifests)
    |
    v
getProjectFiles.py  (extracts data; -f re-pulls from LIMS)
    |
    +-> Proj_<ID>_metadata.yaml        (request-level metadata)
    +-> Proj_<ID>_sample_mapping.txt   (sample-to-FASTQ mappings, TSV)
    +-> Proj_<ID>_metadata_samples.csv (detailed sample metadata)
    |
    v
R pipeline scripts consume these files:
  makeVariantProject.R  -> _request, pairing_manifest.xlsx, sample_grouping.txt
  makeRNASeqProject.R   -> sample_key.xlsx, sample_key.tsv
  makeChIPSeqProject.R  -> ChIP-seq project files
```

### Python Layer

- **limsETL.py**: Core library. Classes (`Sample`, `RequestSamples`, `SampleManifest`, `Library`, `Run`, `MachineRuns`) wrap LIMS JSON responses by assigning `__dict__` directly from JSON. API functions (`getRequestSamples`, `getSampleManifest`, `getDeliveries`) call `settings.LIMS_ROOT_URL` with basic auth. `get_request_samples_json` and `get_sample_manifest_json` return the raw JSON that the object functions wrap.
- **limsDB.py**: Local SQLite store. Tables `requests` and `sample_manifests` hold raw LIMS JSON with an ISO 8601 `pulled_at`; views `v_requests`, `v_request_samples`, `v_samples`, `v_fastqs` expose fields as columns. Path is `settings.LIMS_DB_PATH` if set, else `limsDB.sqlite` in the code directory. Uses the default rollback journal, not WAL, because the DB may be on a network filesystem. `PRAGMA user_version` is the schema version; bump `SCHEMA_VERSION` when tables or views change. LIMS writes missing values in several ways; `MISSING_TEXT` (`""`, `null`, `none`, `na`, `n/a`, matched after trimming spaces, any case) lists the text forms. The views return them as NULL and `clean_missing()` sets them to None in parsed JSON. The stored JSON is left as LIMS sent it.
- **getProjectFiles.py**: Main entry point. Filters to primary IGO IDs only (regex `^<projectNo>_\d+$`). If the request is in the local DB, uses it (no request call) and pulls only complete samples missing from it; otherwise, or with `-f`, pulls from LIMS and replaces the stored request and its manifests. Output files are built from the same JSON either way, after `limsDB.clean_missing()`; missing values are written as empty fields in the CSV and `""` in the YAML. Failed sample pulls are not stored; those samples are left out of all outputs, and complete ones are reported on stderr with exit 1. Complete samples with no FASTQ files are reported the same way. A run from a local copy warns when samples were incomplete at pull time.
- **dumpLimsDB.py**: Exports the four views to `<OUT>_<YYMMDD>.xlsx` (one sheet per view, via openpyxl) and `<OUT>_<YYMMDD>_<view>.csv`, with the date of the dump; names drop the `v_` prefix. NULL is written as an empty field or cell. `-d` sets the database, `-o` the output prefix (default `lims/limsDB`, so files go in `./lims/`, created if needed). Exits 1 if the database does not exist.
- **conf.py**: Credentials (git-ignored). Copy from `conf.py.tmpl`.

### Zone-Aware Path Handling

FASTQ paths differ between compute zones. `get_zone_from_env()` reads `CDC_JOINED_ZONE` env var to detect JUNO vs IRIS. On IRIS, JUNO paths are rewritten to IRIS_ROOT. Zone detection uses `startswith("IRIS")` for variant tolerance.

### R Layer

R scripts source `tools.R` (from `/home/socci/Code/LIMS/LimsETL/tools.R` -- hardcoded path). `makeVariantProject.R` maps LIMS bait sets to pipeline assay names via a translation table and validates against `knownTargets`. Dependencies: `yaml`, `tidyverse`, `openxlsx`, `fs`.

### Wrapper Script

`createBICProject.sh` determines pipeline type from parent directory name (`variant`/`chipseq`/`rnaseq`), runs `getProjectFiles.py`, then dispatches to the appropriate R script.

## Common Commands

```bash
# Extract project data (local copy if stored, else LIMS)
./getProjectFiles.py <PROJECT_NUMBER>

# Force a re-pull from LIMS and replace the local copy
./getProjectFiles.py -f <PROJECT_NUMBER>

# Export the local database views to Excel and CSV
./dumpLimsDB.py [-d DB] [-o OUT_PREFIX]

# Rewrite FASTQ paths to a new root (stdin if no file; writes stdout)
./resetFASTQRoot /new/root/FASTQ [Proj_<ID>_sample_mapping.txt]

# Full pipeline (run from Proj_<ID> directory inside variant/chipseq/rnaseq)
./createBICProject.sh

# Individual R pipeline scripts
Rscript --no-save makeVariantProject.R Proj_<ID>_metadata.yaml
Rscript --no-save makeRNASeqProject.R Proj_<ID>_metadata.yaml

# Merge multiple requests into one project
Rscript --no-save mergeRequests.R
```

### Testing

```bash
cd UnitTests
./doUnitTest01.sh
```

Regression tests: re-generates `sample_mapping.txt` for each project in `Targets/`, sorts output, and diffs against stored baselines. Results logged to `log_unitTest01_<date>`.

## Dependencies

**Python**: `requirements.txt` -- `urllib3==1.26.12`, `requests==2.28.1`, `openpyxl==3.1.5` (dumpLimsDB.py only). `sqlite3` from the standard library (SQLite with JSON functions).
**R**: `yaml`, `tidyverse`, `openxlsx`, `fs`.
**Virtual env**: `venv3/` (git-ignored).

## Key Conventions

- Output files: `Proj_<RequestId>_<type>.<ext>` (all git-ignored)
- Local database: `limsDB.sqlite` (git-ignored). The old cachier `__cache__/` dirs are no longer used
- IGO ID filtering: only primary IDs (e.g., `12345_A_1`) are processed; secondary IDs (e.g., `12345_B_1_1`) are skipped
- Missing values: LIMS text in `limsDB.MISSING_TEXT` is treated as null. `sex = "Unknown"` is a real LIMS value and is kept
- Null handling: when investigatorSampleId is null it is derived from the FASTQ path, then sampleName, cmoSampleName, or igoId
