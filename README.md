# Albany

## Version 2.1.0

LimsETL is a bioinformatics data extraction and processing pipeline that interfaces with IGO LIMS (Laboratory Information Management System) to retrieve genomic project metadata and generate standardized project files for downstream analysis pipelines.

## Features

- Extract project metadata from IGO LIMS via REST API
- Generate pipeline-specific project files for variant calling, RNA-seq, and ChIP-seq
- Support for multiple sequencing zones (JUNO, IRIS) with dynamic path handling
- Automated sample-to-FASTQ mapping with comprehensive metadata
- Request merging capabilities for multi-request projects

## Installation

### Prerequisites
- Python 3.x
- R (for pipeline project generation)
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
python3 getProjectFiles.py <PROJECT_NUMBER>
python3 getProjectFiles.py -f <PROJECT_NUMBER>   # re-pull from LIMS
```
Generates three output files:
- `Proj_<ID>_metadata.yaml`: Project-level metadata
- `Proj_<ID>_sample_mapping.txt`: Sample-to-file mappings  
- `Proj_<ID>_metadata_samples.csv`: Detailed sample metadata

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

```r
con <- DBI::dbConnect(RSQLite::SQLite(), "limsDB.sqlite")
dplyr::tbl(con, "v_samples")
```

To export the views as flat tables:
```bash
python3 dumpLimsDB.py              # lims/limsDB_<YYMMDD>.xlsx, lims/limsDB_<YYMMDD>_<view>.csv
python3 dumpLimsDB.py -o out/lims  # out/lims_<YYMMDD>.xlsx, out/lims_<YYMMDD>_<view>.csv
```
`<YYMMDD>` is the date of the dump. The default output directory is
`./lims/`, created if needed. The workbook has one sheet per view,
and there is one CSV file per view, named without the `v_` prefix.
`-d` selects a different database.

### Key Features
- Environment zone detection for FASTQ path resolution
- Local SQLite copy of LIMS data for fast repeat runs and queries
- Robust null value handling in metadata parsing
- Primary IGO ID validation to prevent duplicates

## Testing
```bash
cd UnitTests
./doUnitTest01.sh
```

