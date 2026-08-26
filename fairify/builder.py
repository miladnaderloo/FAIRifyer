"""
builder.py
----------
Responsible for assembling the final structured metadata record and producing
the conceptual (human-readable) view of it.

  - build_structured_metadata : combines all pipeline outputs into the
                                 EXCITE JSON record that gets written to disk
  - map_to_concepts           : groups technical fields into named concepts
                                 (energy, sample_positioning, reconstruction…)

Imports schema.py for the field lists. No AI or file I/O here.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .schema import EXCITE_ACQ_KEYS, EXCITE_EXTENDED_KEYS, EXCITE_REC_KEYS


# ---------------------------------------------------------------------------
# Conceptual view
# ---------------------------------------------------------------------------

def _quantity(value, unit: str):
    """
    Wrap a physical value with its unit for FAIR output.
    Returns None if value is None so missing fields stay null.

    Example:  _quantity(140.0, "kV")  →  {"value": 140.0, "unit": "kV"}
    """
    if value is None:
        return None
    return {"value": value, "unit": unit}


def map_to_concepts(normalized: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert the flat, technical EXCITE parameter dict into a grouped,
    human-readable conceptual view aligned with the EXCITE data model.

    Every physical quantity is represented as {"value": ..., "unit": "..."}
    so the output is fully self-describing and FAIR-compliant.

    This is intentionally a *view* — it does not replace the structured
    record; it lives alongside it as "conceptual_metadata".
    """
    conceptual: Dict[str, Any] = {}

    # --- Sample positioning (geometry group) ---
    sod = normalized.get("source_object_distance_mm")
    odd = normalized.get("object_detector_distance_mm")
    sdd = normalized.get("source_detector_distance_mm")
    if any(v is not None for v in [sod, odd, sdd]):
        conceptual["sample_positioning"] = {
            "source_object_distance":   _quantity(sod, "mm"),
            "object_detector_distance": _quantity(odd, "mm"),
            "source_detector_distance": _quantity(sdd, "mm"),
        }

    # --- Core acquisition ---
    conceptual["optical_magnification"] = _quantity(normalized.get("optical_magnification"), "x")
    conceptual["energy"]                = _quantity(normalized.get("tube_voltage_kV"),       "kV")
    conceptual["power"]                 = _quantity(normalized.get("tube_power_W"),           "W")
    conceptual["current"]               = _quantity(normalized.get("tube_current_uA"),       "uA")
    # Use ms-keyed value first (from "Exposure time (ms)" vendor key), fall back to _s
    _exp = normalized.get("time_per_exposure_ms") or normalized.get("time_per_exposure_s")
    conceptual["exposure_time"]         = _quantity(_exp, "s")
    # Priority: dedicated voxel_size_um → mm-converted → generic um value
    _vox = (normalized.get("projection_image_voxel_size_um")
            or normalized.get("projection_image_pixel_size_mm")
            or normalized.get("projection_image_pixel_size_um"))
    conceptual["voxel_size"]            = _quantity(_vox, "um")
    conceptual["total_num_projections"] = _quantity(normalized.get("total_num_projections"), "count")
    # Priority: precise "Duration" (HH:MM:SS) → approximate "SCAN DURATION"
    _scan_time = (normalized.get("total_acquisition_time_s")
                  or normalized.get("total_acquisition_time_approx_s"))
    conceptual["total_scan_time"]       = _quantity(_scan_time, "s")
    
    # --- Optional acquisition ---
    conceptual["aperture_filter"] = normalized.get("aperture_filter")  # free text, no unit
    conceptual["scanning_mode"]   = normalized.get("scanning_mode")    # vendor string, no unit

    # --- Image size ---
    w = normalized.get("projection_image_width_px")
    h = normalized.get("projection_image_height_px")
    if w or h:
        conceptual["image_size"] = {
            "width":  _quantity(w, "px"),
            "height": _quantity(h, "px"),
        }

    # --- Reconstruction block ---
    conceptual["reconstruction"] = {
        "algorithm":                normalized.get("reconstruction_algorithm"),
        "filter":                   normalized.get("filter"),
        "center_shift":             _quantity(normalized.get("center_shift"),   "px"),
        "beam_hardening_algorithm": normalized.get("beam_hardening_correction_algorithm"),
        "rotation_angle":           _quantity(normalized.get("rotation_angle"), "deg"),
        "grey_level":               normalized.get("grey_level"),
    }

    return conceptual


# ---------------------------------------------------------------------------
# Structured record assembly
# ---------------------------------------------------------------------------

def build_structured_metadata(
    translated: Dict[str, Any],
    provenance: Dict[str, List[str]],
    dataset_path: Path,
) -> Dict[str, Any]:
    """
    Assemble the complete EXCITE metadata record from the translated,
    normalised dict.

    The output dict has the following top-level keys:

      @context          — Linked Data context (schema.org + EXCITE namespace)
      type              — record type identifier
      generated_at      — ISO 8601 timestamp of when this record was created
      dataset_path      — absolute path of the source dataset
      acquisition       — all EXCITE_ACQ_KEYS (None where not found)
      reconstruction    — all EXCITE_REC_KEYS (None where not found)
      extended          — EXCITE_EXTENDED_KEYS that were found
      missing_fields    — sorted list of ACQ + REC keys that were not found
      provenance        — {raw_key: [source_files]}
      raw_unmapped      — keys that could not be mapped to any canonical field
    """
    acq: Dict[str, Any] = {k: None for k in EXCITE_ACQ_KEYS}
    rec: Dict[str, Any] = {k: None for k in EXCITE_REC_KEYS}
    missing: List[str] = []

    for k in acq:
        if k in translated:
            acq[k] = translated[k]
        else:
            missing.append(k)

    for k in rec:
        if k in translated:
            rec[k] = translated[k]
        else:
            missing.append(k)

    extended: Dict[str, Any] = {
        k: translated[k]
        for k in EXCITE_EXTENDED_KEYS
        if k in translated
    }

    return {
        "@context": {
            "schema": "https://schema.org/",
            "excite": "https://example.org/excite#",
        },
        "type": "CTImagingDatasetMetadata",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "dataset_path": str(dataset_path),
        "acquisition": acq,
        "reconstruction": rec,
        "extended": extended,
        "missing_fields": sorted(set(missing)),
        "provenance": provenance,
        "raw_unmapped": translated.get("__unmapped__", {}),
    }
