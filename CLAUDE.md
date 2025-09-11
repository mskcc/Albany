# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
LimsETL is a bioinformatics data extraction and processing pipeline that interfaces with IGO LIMS (Laboratory Information Management System) to retrieve genomic project metadata and generate standardized project files for downstream analysis pipelines.

## Core Architecture

### Python Components
- **limsETL.py**: Core LIMS interface library containing classes for API communication
  - `RequestSamples`: Container for project request data with sample collections
  - `Sample`: Individual sample metadata wrapper 
  - `SampleManifest`: Complete sample metadata with sequencing details
  - `Library`: Sequencing library information with runs
  - `Run`: Sequencing run data with FASTQ file paths
- **getProjectFiles.py**: Main executable script for extracting project data from LIMS
- **conf.py**: Configuration file containing LIMS API credentials and endpoints

### R Components  
- **makeVariantProject.R**: Creates variant calling pipeline project files from LIMS metadata
- **makeRNASeqProject.R**: Generates RNA-seq analysis project structure from LIMS data
- **makeChIPSeqProject.R**: Sets up ChIP-seq analysis project files
- **mergeRequests.R**: Combines multiple IGO requests into single project
- **tools.R**: Common R utility functions

## Common Commands

### Data Extraction
```bash
# Extract project data from LIMS by project number
python3 getProjectFiles.py <PROJECT_NUMBER>

# Example: Extract data for project 12345_A  
python3 getProjectFiles.py 12345_A
```

### Project File Generation
```bash
# Create variant calling project files
./makeVariantProject.R Proj_<PROJECT_NUMBER>_metadata.yaml

# Create RNA-seq project files
./makeRNASeqProject.R Proj_<PROJECT_NUMBER>_metadata.yaml
```

### Testing
```bash
# Run unit tests (from UnitTests directory)
cd UnitTests
./doUnitTest01.sh
```

## Configuration
- Copy `conf.py.tmpl` to `conf.py` and configure LIMS credentials
- The `.netrc` file is used for additional authentication
- Virtual environment setup: `venv3/` contains Python dependencies

## Data Flow
1. **getProjectFiles.py** queries LIMS API for project metadata
2. Generates three output files per project:
   - `Proj_<ID>_metadata.yaml`: Project-level metadata  
   - `Proj_<ID>_sample_mapping.txt`: Sample-to-file mappings
   - `Proj_<ID>_metadata_samples.csv`: Detailed sample metadata
3. R scripts consume these files to create pipeline-specific project structures

## Key Data Structures
- Projects contain multiple samples with unique IGO IDs
- Each sample can have multiple sequencing libraries  
- Libraries contain runs with associated FASTQ file paths
- Caching is implemented via the `cachier` library for API calls

## File Patterns
- Project files follow naming convention: `Proj_<ProjectNumber>_<type>.<ext>`
- Test data stored in `Tests/` and `UnitTests/` directories
- Configuration files and credentials are git-ignored