# Albany

## Version 2.1.0

LimsETL retrieves genomic project metadata from IGO LIMS (Laboratory Information Management System), keeps a local SQLite copy of it, and writes standardized project files for downstream analysis pipelines.

## Features

- Extract project metadata from IGO LIMS via REST API
- Store pulled data in a local SQLite database and export it to xlsx and CSV
- Write a sample-to-FASTQ mapping and sample metadata for each project
- Support for multiple sequencing zones (JUNO, IRIS) with dynamic path handling
- Rewrite the FASTQ root of a mapping file

## Installation

### Prerequisites
- Python 3.10 or later
- Access to IGO LIMS system

### Setup
1. Clone repository
2. Install Python dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```
3. Configure LIMS credentials:
   ```bash
   cp conf.py.tmpl conf.py
   ```
   Edit `conf.py` and set:
   ```python
   self.LIMS_USERNAME="your_username"
   self.LIMS_PASSWORD="your_password"
   ```

## Usage

### Extract Project Data
```bash
./getProjectFiles.py <PROJECT_NUMBER>
./getProjectFiles.py -f <PROJECT_NUMBER>   # re-pull from LIMS
```
Generates three output files:
- `Proj_<ID>_metadata.yaml`: Project-level metadata
- `Proj_<ID>_sample_mapping.txt`: Sample-to-file mappings
- `Proj_<ID>_metadata_samples.csv`: Detailed sample metadata

### Change the FASTQ Root
```bash
./resetFASTQRoot /new/root/FASTQ Proj_<ID>_sample_mapping.txt >new_mapping.txt
```
Replaces the part of each FASTQ path up to the first `/FASTQ/` with
the new root. Reads stdin if no file is given and writes to stdout.

### Local LIMS Database
Every request pulled from LIMS is stored, with its sample manifests
and the pull time, in a local SQLite database (`limsDB.sqlite` in the
code directory; set `LIMS_DB_PATH` in `conf.py` to move it).

- If the request is already stored, `getProjectFiles.py` uses the
  local copy and prints the date it was pulled. Complete samples
  missing from the local copy are pulled from LIMS and added.
- If the local copy has samples that were incomplete when pulled, a
  warning suggests `-f`.
- `-f`/`--force` pulls the request from LIMS again and replaces the
  local copy and its date.

The database stores the raw LIMS JSON. These views expose common
fields as columns for queries from Python or R:

| View | One row per |
|---|---|
| `v_requests` | request |
| `v_request_samples` | sample listed in a request, with `igoComplete` |
| `v_samples` | stored sample manifest, with sample metadata |
| `v_fastqs` | FASTQ file, with library and run |

LIMS writes a missing value in several ways: JSON null, `""`, `null`,
`N/A`, `NA`, `na`. The views return all of them as NULL, and
`getProjectFiles.py` writes them as empty values. `sex = "Unknown"` is
kept as a value.

```r
con <- DBI::dbConnect(RSQLite::SQLite(), "limsDB.sqlite")
dplyr::tbl(con, "v_samples")
```

To export the views as flat tables:
```bash
./dumpLimsDB.py              # lims/limsDB_<YYMMDD>.xlsx, lims/limsDB_<YYMMDD>_<view>.csv
./dumpLimsDB.py -o out/lims  # out/lims_<YYMMDD>.xlsx, out/lims_<YYMMDD>_<view>.csv
```
`<YYMMDD>` is the date of the dump. The default output directory is
`./lims/`, created if needed. The workbook has one sheet per view,
and there is one CSV file per view, named without the `v_` prefix.
`-d` selects a different database.

### Key Features
- Environment zone detection for FASTQ path resolution
- Local SQLite copy of LIMS data for fast repeat runs and queries
- One empty value for every form of missing LIMS data
- Primary IGO ID validation to prevent duplicates

## Testing
```bash
cd UnitTests
./doUnitTest01.sh
```

## Retired Code
The legacy R project scripts (`makeVariantProject.R`,
`makeRNASeqProject.R`, `makeChIPSeqProject.R`, `mergeRequests.R`) and
the `createBICProject.sh` wrapper are in `attic/` for reference. They
are no longer maintained.

