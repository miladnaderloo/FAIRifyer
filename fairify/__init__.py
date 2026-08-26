"""
fairify
-------
AI-assisted metadata extractor for CT/imaging datasets.

Public API
----------
    from fairify import fairify
    from fairify import fairify_with_readme
    from fairify import fairify_excite2

The full pipeline:
    find files → parse → translate terms → normalise units → build record

fairify_excite2() is a second, parallel pipeline that structures the
output around the EXCITE2 network's own graph data model (nodes: sample,
site, operator, instrument, software, license; edges: sampling,
sample_processing, measuring) instead of the flat acquisition/
reconstruction/extended blocks used by fairify(). It does not replace
fairify(); both are available side by side.
"""

from pathlib import Path
from typing import Any, Dict, Union
import json

from .builder import build_structured_metadata, map_to_concepts
from .builder_excite2 import build_excite2_record
from .normaliser import normalize_units
from .parsers import find_metadata_files, harvest_pairs
from .translator import translate_terms
from .validator import validate_conceptual, validate_excite2
from .readme_generator import generate_readme


def fairify(dataset_path: Union[str, Path]) -> Dict[str, Any]:
    """Run the full FAIRification pipeline on a dataset folder."""
    root = Path(dataset_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Dataset folder not found: {root}")

    files                      = find_metadata_files(root)
    raw_pairs, provenance      = harvest_pairs(files)
    translated, similarities   = translate_terms(raw_pairs)
    normalized                 = normalize_units(translated)
    conceptual                 = map_to_concepts(normalized)
    structured                 = build_structured_metadata(normalized, provenance, root)

    structured["conceptual_metadata"] = conceptual
    structured["similarity_scores"]   = similarities

    try:
        report = validate_conceptual(conceptual)
        structured["validation"] = report.to_dict()
    except FileNotFoundError:
        structured["validation"] = {"error": "Schema file not found — validation skipped."}

    return structured


def fairify_with_readme(
    dataset_path: Union[str, Path],
    json_out: str = "metadata_excite.json",
    readme_out: str = "README.txt",
) -> Dict[str, Any]:
    """
    Run the full FAIRification pipeline AND generate a README.txt
    alongside the JSON output.
    """
    structured = fairify(dataset_path)
    Path(json_out).write_text(json.dumps(structured, indent=2), encoding="utf-8")
    generate_readme(structured, output_path=readme_out)
    return structured


def fairify_excite2(dataset_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Run the FAIRification pipeline and return a record structured around
    the EXCITE2 graph data model (Deliverable D4.2, Appendix I), instead
    of the flat acquisition/reconstruction/extended blocks used by
    fairify().

    This is EXTRACTION ONLY: every field is either filled from a real
    vendor key found in the dataset's files, or left null. No manual
    entry, no second input channel.

    Returns
    -------
    dict with keys: @context, type, schema_version, generated_at,
    dataset_path, nodes (sample/site/operator/instrument/software/license),
    edges (sampling/sample_processing/measuring), extraction_coverage,
    provenance, raw_unmapped.
    """
    root = Path(dataset_path).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"Dataset folder not found: {root}")

    files                 = find_metadata_files(root)
    raw_pairs, provenance = harvest_pairs(files)
    translated, _         = translate_terms(raw_pairs)
    normalized            = normalize_units(translated)

    record = build_excite2_record(
        raw_keys=raw_pairs,
        translated=normalized,
        provenance=provenance,
        dataset_path=root,
    )
    try:
        report = validate_excite2(record)
        record["validation"] = report.to_dict()
    except FileNotFoundError:
        record["validation"] = {"error": "Schema file not found — validation skipped."}
    return record


__all__ = [
    "fairify",
    "fairify_with_readme",
    "fairify_excite2",
    "generate_readme",
    "build_excite2_record",
]
