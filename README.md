# Albany

## Version 2.0.1

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
```
Generates three output files:
- `Proj_<ID>_metadata.yaml`: Project-level metadata
- `Proj_<ID>_sample_mapping.txt`: Sample-to-file mappings  
- `Proj_<ID>_metadata_samples.csv`: Detailed sample metadata

### Key Features
- Environment zone detection for FASTQ path resolution
- Caching via `cachier` library for API performance
- Robust null value handling in metadata parsing
- Primary IGO ID validation to prevent duplicates

## Testing
```bash
cd UnitTests
./doUnitTest01.sh
```

