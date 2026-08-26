# Changelog

All notable changes to FAIRifyer are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-08-26

First public release.

### Added

- Full FAIRification pipeline: find files, parse, translate terms, normalise
  units, build record, validate.
- Two-stage term translation: regex against a curated synonym table, with
  sentence-transformer embeddings for unseen vendor keys and a `difflib`
  fallback when the model is not installed.
- `fairify()` flat output with acquisition, reconstruction and extended blocks.
- `fairify_excite2()` output structured around the EXCITE² graph data model
  (deliverable D4.2), extraction only.
- `fairify_with_readme()` producing a deposit-ready `README.txt` following EPFL
  Library README best practices.
- Versioned JSON Schemas for both output shapes, with validation reports and
  completeness scoring.
- Optional sidecar file for fields that cannot be extracted from vendor logs,
  which never overwrites real scanner data.
- Command line interface: `fairify <dataset> --out <file>`.

[Unreleased]: https://github.com/miladnaderloo/FAIRifyer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/miladnaderloo/FAIRifyer/releases/tag/v0.1.0
