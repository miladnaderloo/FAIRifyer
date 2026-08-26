"""
builder_excite2.py
-------------------
Assembles the final metadata record structured around the EXCITE2 graph
data model (NODES: sample, site, operator, instrument, software, license
+ EDGES: sampling, sample_processing, measuring), instead of the flat
acquisition/reconstruction/extended blocks used previously.

This REPLACES build_structured_metadata() from the old builder.py for the
purpose of EXCITE2 schema alignment. The old CT-physics conceptual view
(map_to_concepts) is still reused unchanged inside the measuring edge,
since that work already covers CT acquisition parameters well.

Goal right now: EXTRACTION ONLY. Every field comes straight from the
`translated` dict already produced by the existing parser/translator
pipeline. If a field's pattern matched something, it is filled. If not,
it stays null. No manual entry. No second input channel. Coverage stats
are computed from schema_excite2.py so the output is self-documenting
about what could and could not be extracted from CT scanner files alone.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from .sidecar import read_sidecar

from .schema_excite2 import (
    SAMPLE_FIELDS, SITE_FIELDS, OPERATOR_FIELDS, INSTRUMENT_FIELDS,
    SOFTWARE_FIELDS, LICENSE_FIELDS, SAMPLING_EDGE_FIELDS,
    SAMPLE_PROCESSING_EDGE_FIELDS, MEASURING_EDGE_FIELDS,
    extraction_coverage_report,
)
from .builder import map_to_concepts  # reuse existing CT physics conceptual view


def _clean_value(value: Any) -> Any:
    """
    Strip stray escaped quote characters left over from vendor file
    parsing (e.g. raw value '"Peter"' -> 'Peter') and try to coerce
    numeric-looking strings into real numbers (e.g. '3.172302' -> 3.172302).
    Leaves non-string values and genuinely non-numeric strings untouched.
    """
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip().strip('"').strip("'").strip()
        if cleaned == "":
            return None
        try:
            if "." in cleaned or "e" in cleaned.lower():
                return float(cleaned)
            return int(cleaned)
        except ValueError:
            return cleaned
    return value


def _unit_from_key_name(raw_key: str) -> Optional[str]:
    """
    Pull a unit out of a vendor key name when the unit is embedded there
    rather than stored separately, e.g. 'Diameter (mm)' -> 'mm'.
    Returns None if no parenthesised unit is found.
    """
    match = re.search(r"\(([a-zA-Z%]+)\)", raw_key)
    return match.group(1) if match else None


def _dimension_type_from_key(raw_key: str) -> str:
    """
    Return the raw key name itself, not a guessed physical interpretation.

    CORRECTED: this previously tried to classify the key as "diameter",
    "height", or "sample_size" based on keyword matching. That was wrong:
    the real vendor files contain TWO DIFFERENT keys for the exact same
    value (3.172302) -- "Diameter (mm)" in Acquisition_settings_XRE.txt
    and "Sample size" in scan_settings.txt. These files contradict each
    other and there is no way to know from the data alone which physical
    measurement (diameter vs length vs something else) this actually is.
    Asserting "diameter" was an unverified guess presented as a fact.
    The honest approach is to report the raw key name verbatim and let
    the researcher, who knows the actual sample, interpret it correctly.
    """
    return raw_key.strip()


def _extract_field(raw_keys: Dict[str, Any], field_def: Dict[str, Any]) -> Optional[Any]:
    """
    Try to extract one field's value from the raw (untranslated) key dict
    using the field's regex pattern. Returns None if not extractable or
    no raw key matched.

    raw_keys is the dict of ORIGINAL vendor key -> value, before EXCITE
    translation, e.g. {"Sample name": "Alpine mylonite", "Operator": "admin", ...}

    If field_def["unit_from_key"] is True, the unit is pulled from the
    matched raw key's name (e.g. "Diameter (mm)" -> unit "mm") and the
    result is returned as {value, unit, dimension_type} instead of a bare
    number, so the unit is never silently discarded.
    """
    if not field_def.get("extractable"):
        return field_def.get("constant_value")  # None unless explicitly asserted

    pattern = field_def.get("pattern")
    if pattern is None:
        return _clean_value(field_def.get("constant_value"))

    compiled = re.compile(pattern, re.IGNORECASE)
    for raw_key, raw_value in raw_keys.items():
        if compiled.search(str(raw_key)):
            cleaned = _clean_value(raw_value)
            if field_def.get("unit_from_key"):
                return {
                    "value": cleaned,
                    "unit": _unit_from_key_name(str(raw_key)),
                    "dimension_type": _dimension_type_from_key(str(raw_key)),
                }
            return cleaned
    return None


def _build_node(raw_keys: Dict[str, Any], field_defs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Build one node's dict: {field_name: extracted_value_or_None}."""
    return {name: _extract_field(raw_keys, defn) for name, defn in field_defs.items()}


def build_excite2_record(
    raw_keys: Dict[str, Any],
    translated: Dict[str, Any],
    provenance: Dict[str, List[str]],
    dataset_path: Path,
) -> Dict[str, Any]:
    """
    Assemble the EXCITE2 graph-structured metadata record.

    Parameters
    ----------
    raw_keys     : original vendor key -> value dict, BEFORE translation
                   (needed because several EXCITE2 fields, e.g. Operator.name,
                   map from the raw vendor key directly, not from the
                   already-translated CT-physics field names)
    translated   : the existing translated/normalised dict, reused for the
                   measuring edge's "parameters" (CT acquisition physics)
    provenance   : {raw_key: [source_files]}, unchanged from existing pipeline
    dataset_path : path to the dataset folder

    Returns
    -------
    dict with one key per graph node/edge, plus coverage stats and the
    usual @context / generated_at / provenance bookkeeping.
    """
    sample = _build_node(raw_keys, SAMPLE_FIELDS)
    site = _build_node(raw_keys, SITE_FIELDS)
    operator = _build_node(raw_keys, OPERATOR_FIELDS)
    instrument = _build_node(raw_keys, INSTRUMENT_FIELDS)
    software = _build_node(raw_keys, SOFTWARE_FIELDS)
    license_ = _build_node(raw_keys, LICENSE_FIELDS)
    



    sampling_edge = _build_node(raw_keys, SAMPLING_EDGE_FIELDS)
    sample_processing_edge = _build_node(raw_keys, SAMPLE_PROCESSING_EDGE_FIELDS)

    # Measuring edge is special: its "parameters" field is the existing,
    # already-working CT acquisition conceptual view, not a single raw key.
    measuring_edge = _build_node(raw_keys, MEASURING_EDGE_FIELDS)
    measuring_edge["parameters"] = map_to_concepts(translated)

# Overlay any values supplied by the manually-filled sidecar file
    # (Site, License, Sample type/material -- fields a scanner can
    # never record on its own). Only fills in fields that are currently
    # empty; never overwrites something real extracted from the scanner.
    sidecar = read_sidecar(dataset_path)
    if sidecar:
        for section_name, section_dict in [
            ("site", site),
            ("sample", sample),
            ("license", license_),
            ("operator", operator),
            ("instrument", instrument),
            ("software", software),
            ("sampling", sampling_edge),
            ("sample_processing", sample_processing_edge),
        ]:
            sidecar_values = sidecar.get(section_name, {})
            for field_name, field_value in sidecar_values.items():
                if section_dict.get(field_name) is None and field_value:
                    section_dict[field_name] = field_value
    else:
        print(f"Note: no sidecar file found for {dataset_path.name} — "
              f"Site, License, and Sample type/material will stay empty.")
                    
    return {
        "@context": {
            "schema": "https://schema.org/",
            "excite": "https://example.org/excite#",
        },
        "type": "EXCITE2GraphMetadata",
        "schema_version": "excite2_graph_v1 (D4.2 Appendix I)",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset_path": str(dataset_path),

        "nodes": {
            "sample": sample,
            "site": site,
            "operator": operator,
            "instrument": instrument,
            "software": software,
            "license": license_,
        },
        "edges": {
            "sampling": sampling_edge,
            "sample_processing": sample_processing_edge,
            "measuring": measuring_edge,
        },

        "extraction_coverage": extraction_coverage_report(),
        "provenance": provenance,
        "raw_unmapped": translated.get("__unmapped__", {}),
    }
