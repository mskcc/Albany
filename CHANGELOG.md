# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased] - 2025-09-11

### Added
- Environment zone detection utility in `limsETL.py` with `get_zone_from_env()` function
- FASTQ folder root constants for JUNO and IRIS zones
- Claude Code project documentation (`CLAUDE.md`)
- Dynamic zone detection for path replacement

### Changed
- Enhanced FASTQ path handling with zone-aware path replacement
- Improved project output formatting to use f-strings
- Updated IRIS zone detection to use prefix matching instead of exact match
- Refactored path handling for better IRIS zone compatibility

### Fixed
- IRIS zone detection now handles zone variants robustly using `startswith("IRIS")`
- Null value handling in sample metadata parsing for species, baitSet, and investigatorSampleId fields
- Auto-generation of investigatorSampleId from file path when missing

## [2024-01-31]

### Changed
- Added configuration module setup check in `limsETL.py`

## [2024-01-12]

### Added
- Draft pairing manifest file creation in `makeVariantProject.R`
- Long format pairing workflow: SampleID,PatientID,Type
- SSHFuse file ignore pattern (._* files) in `.gitignore`

### Changed
- Enhanced pairing workflow to support editable manifest files
- Pipeline pairing file generation from manifest

### Fixed
- Primary IGO ID validation to handle duplicate/redundant IGO IDs
- Prevention of duplication issues from non-primary IGO IDs (e.g., 12345_B_1_1)
- Filtering to ensure only primary IGO IDs are processed

## [2024-01-12] - Starting Point (8c8116d)

Base merge from development branch including:
- Project file extraction improvements
- Variant calling project file generation enhancements
- Request merging functionality
- Known targets configuration updates