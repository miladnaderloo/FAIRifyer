"""
normaliser.py
-------------
Responsible for converting raw extracted values into consistent units and types.

  - _to_numeric     : extract a number from a string, optionally applying a
                      unit-based scale factor (e.g. "80 ms" → 0.08 s)
  - _parse_iso_like : coerce vendor timestamp strings to ISO 8601
  - UNIT_NORMALIZERS: per-field conversion lambdas
  - normalize_units : apply all conversions to a translated dict
  - Special cases   : "WxH" image-size strings, "Al 1 mm" filter strings

No schema knowledge or AI logic lives here.
"""

import re
from datetime import datetime
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _to_numeric(
    value: Any,
    scale: Optional[Dict[str, float]] = None,
) -> Optional[float]:
    """
    Extract the first number from *value* and optionally scale it.

    Examples
    --------
    _to_numeric("80 ms", {"ms": 0.001, "s": 1.0})  → 0.08
    _to_numeric("3*4")                               → 12.0
    _to_numeric("none")                              → None
    """
    if value is None:
        return None

    text = str(value).strip().lower()

    # Handle "a * b" composite values (e.g. "2048*2048")
    if "*" in text:
        try:
            prod = 1.0
            for part in re.split(r"\*", text):
                nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", part)
                if not nums:
                    return None
                prod *= float(nums[0])
            return prod
        except Exception:
            pass

    numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    num = float(numbers[0]) if numbers else None

    if scale and num is not None:
        unit_match = re.search(r"([a-zµ°]+)$", text)
        unit = unit_match.group(1) if unit_match else None
        if unit and unit in scale:
            return num * scale[unit]

    return num


def _parse_hhmmss(duration: Any) -> Optional[float]:
    """
    Parse a HH:MM:SS duration string into total seconds.
    Example: "00:35:31" → 2131.0 seconds
    """
    if duration is None:
        return None
    s = str(duration).strip().strip('"').strip("'")
    import re
    m = re.match(r"(\d+):(\d+):(\d+)", s)
    if m:
        h, mn, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return float(h * 3600 + mn * 60 + sec)
    return _to_numeric(s, {"s": 1.0, "min": 60.0, "minutes": 60.0, "h": 3600.0})


def _parse_iso_like(ts: Any) -> str:
    """
    Coerce a vendor timestamp string to ISO 8601 (UTC).
    Falls back to returning the input unchanged if parsing fails.

    Supported input formats
    -----------------------
    "2024-03-15 10:23:45.123456"
    "2024-03-15 10:23:45"
    "2024/03/15 10:23:45"
    (with optional trailing "UTC")
    """
    if ts is None:
        return ts
    s = str(ts).strip().strip('"').replace("UTC", "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).isoformat() + "Z"
        except Exception:
            continue
    return str(ts)


# ---------------------------------------------------------------------------
# Per-field conversion table
# ---------------------------------------------------------------------------

UNIT_NORMALIZERS: Dict[str, Any] = {
    # Physical quantities — normalise to canonical unit
    "tube_voltage_kV":              lambda v: _to_numeric(v, {"v": 0.001, "kv": 1.0}),
    "tube_power_W":                 lambda v: _to_numeric(v, {"w": 1.0}),
    "tube_current_uA":              lambda v: _to_numeric(v, {"ma": 1000.0, "ua": 1.0}),
    "aperture_filter_thickness_mm": lambda v: _to_numeric(v, {"mm": 1.0}),
    # "Exposure time (ms)" key — value is already in ms, force conversion
    "time_per_exposure_ms":         lambda v: _to_numeric(v) * 0.001 if _to_numeric(v) is not None else None,
    "time_per_exposure_s":          lambda v: _to_numeric(v, {"ms": 0.001, "s": 1.0}),
    "total_acquisition_time_s":        lambda v: _parse_hhmmss(v),
    "total_acquisition_time_approx_s": lambda v: _parse_hhmmss(v),
    "projection_image_pixel_size_um": lambda v: _to_numeric(v, {"µm": 1.0, "um": 1.0, "nm": 0.001, "mm": 1000.0}),
    # Pixel size arriving in mm (e.g. "0.023000" from XRE file) → convert to µm
    "projection_image_pixel_size_mm": lambda v: (_to_numeric(v) * 1000.0) if _to_numeric(v) is not None else None,
    # "Voxel size" key value is already in µm (e.g. 22.999979)
    "projection_image_voxel_size_um": lambda v: _parse_voxel_size_um(v),    "total_angular_range_deg":      lambda v: _to_numeric(v, {"deg": 1.0, "°": 1.0}),
    "center_shift":                 lambda v: _to_numeric(v),
    "rotation_angle":               lambda v: _to_numeric(v),
    # Fields that were coming through as strings — force to float
    "source_object_distance_mm":    lambda v: _to_numeric(v),
    "object_detector_distance_mm":  lambda v: _to_numeric(v),
    "source_detector_distance_mm":  lambda v: _to_numeric(v),
    "optical_magnification":        lambda v: _to_numeric(v),
    "total_num_projections":        lambda v: _to_numeric(v),
    "projection_image_height_px":   lambda v: _to_numeric(v),
    "projection_image_width_px":    lambda v: _to_numeric(v),
    "projection_image_bit_depth":   lambda v: _to_numeric(v),
    "exposures_per_projection":     lambda v: _to_numeric(v),
    # Extended fields
    "sample_diameter_mm":           lambda v: _to_numeric(v, {"mm": 1.0}),
    "acquisition_start_time":       _parse_iso_like,
    "acquisition_end_time":         _parse_iso_like,
}

def _parse_voxel_size_um(v: Any) -> Optional[float]:
    """
    Convert a raw "Voxel size" value to micrometres, without needing to
    know which file it came from.

    Some vendor files state the unit explicitly in the value text
    (e.g. "0.004 mm") -- when present, that unit is trusted directly.
    Other vendor files give no unit at all (e.g. "22.999979" or
    "0.023000"). In that case, a magnitude rule is used: CT voxel
    sizes are typically a few to a few hundred micrometres, so a
    unitless value below 1 is implausibly small to already be in
    micrometres, but IS a plausible size in millimetres
    (0.023 mm = 23 um). A unitless value of 1 or more is assumed to
    already be in micrometres.

    This is a domain assumption based on the datasets seen during
    development (Alpine, Ghent), not a certainty -- worth revisiting
    if a dataset with a genuinely unusual voxel size is encountered.
    """
    import re
    if v is None:
        return None
    s = str(v).strip().strip('"').strip("'")

    # Unit stated explicitly in the text -> trust it directly.
    m = re.match(r"^([\d.]+)\s*(mm|µm|um)$", s, flags=re.IGNORECASE)
    if m:
        number = float(m.group(1))
        unit = m.group(2).lower()
        return number * 1000.0 if unit == "mm" else number

    # No unit stated -- fall back to the magnitude rule.
    number = _to_numeric(s)
    if number is None:
        return None
    return number * 1000.0 if number < 1 else number


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_units(translated: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply all unit conversions to a translated metadata dict.

    Also handles two special composite cases:
      - "WxH" image-size strings  → split into width_px / height_px
      - "Al 1 mm" filter strings  → split into material + thickness_mm
    """
    out = dict(translated)

    # Apply per-field numeric / timestamp conversions
    for key, func in UNIT_NORMALIZERS.items():
        if key in out:
            out[key] = func(out[key])

    # Split "1024x1024" or "1024×1024" into separate width / height fields
    wh_key = "projection_image_width_height_px"
    if wh_key in out and isinstance(out[wh_key], str):
        m = re.match(r"\s*(\d+)\s*[x×]\s*(\d+)\s*", out[wh_key].lower())
        if m:
            out["projection_image_width_px"]  = int(m.group(1))
            out["projection_image_height_px"] = int(m.group(2))
        del out[wh_key]

    # Split "Al 1 mm" → material="Al", thickness=1.0
    if "aperture_filter" in out and isinstance(out["aperture_filter"], str):
        m = re.search(r"([A-Za-z]+)\s+([\d\.]+)\s*mm", out["aperture_filter"])
        if m:
            out.setdefault("aperture_filter_material", m.group(1))
            out.setdefault(
                "aperture_filter_thickness_mm",
                _to_numeric(m.group(2) + " mm", {"mm": 1.0}),
            )

    return out
