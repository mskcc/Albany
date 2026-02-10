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
getProjectFiles.py  (extracts data, caches API calls)
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

- **limsETL.py**: Core library. Classes (`Sample`, `RequestSamples`, `SampleManifest`, `Library`, `Run`, `MachineRuns`) wrap LIMS JSON responses by assigning `__dict__` directly from JSON. API functions (`getRequestSamples`, `getSampleManifest`, `getDeliveries`) call `settings.LIMS_ROOT_URL` with basic auth.
- **getProjectFiles.py**: Main entry point. Filters to primary IGO IDs only (regex `^<projectNo>_\d+$`). Uses `cachier` for caching (1-day stale, `__cache__/` dir); gracefully degrades if cachier is unavailable. Creates null records for failed sample fetches rather than aborting.
- **conf.py**: Credentials (git-ignored). Copy from `conf.py.tmpl`.

### Zone-Aware Path Handling

FASTQ paths differ between compute zones. `get_zone_from_env()` reads `CDC_JOINED_ZONE` env var to detect JUNO vs IRIS. On IRIS, JUNO paths are rewritten to IRIS_ROOT. Zone detection uses `startswith("IRIS")` for variant tolerance.

### R Layer

R scripts source `tools.R` (from `/home/socci/Code/LIMS/LimsETL/tools.R` -- hardcoded path). `makeVariantProject.R` maps LIMS bait sets to pipeline assay names via a translation table and validates against `knownTargets`. Dependencies: `yaml`, `tidyverse`, `openxlsx`, `fs`.

### Wrapper Script

`createBICProject.sh` determines pipeline type from parent directory name (`variant`/`chipseq`/`rnaseq`), runs `getProjectFiles.py`, then dispatches to the appropriate R script.

## Common Commands

```bash
# Extract project data from LIMS
python3 getProjectFiles.py <PROJECT_NUMBER>

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

**Python**: `requirements.txt` -- `urllib3==1.26.12`, `requests==2.28.1`. Optional: `cachier`.
**R**: `yaml`, `tidyverse`, `openxlsx`, `fs`.
**Virtual env**: `venv3/` (git-ignored).

## Key Conventions

- Output files: `Proj_<RequestId>_<type>.<ext>` (all git-ignored)
- Cache directory: `__cache__/` (git-ignored)
- IGO ID filtering: only primary IDs (e.g., `12345_A_1`) are processed; secondary IDs (e.g., `12345_B_1_1`) are skipped
- Null handling: missing species/baitSet/investigatorSampleId default to `.NA`; investigatorSampleId auto-derived from FASTQ path when missing
