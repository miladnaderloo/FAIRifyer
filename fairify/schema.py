"""
schema.py
---------
Single source of truth for:
  - EXCITE field lists (acquisition, reconstruction, extended)
  - TERM_SYNONYMS  — regex patterns that map vendor keys → canonical names
  - CANONICAL_FIELDS — merged, deduplicated list used by the AI translator

Nothing in this file does any processing. It is imported by translator.py,
builder.py, and (later) the JSON Schema generator.

CHANGELOG (this version):
  Fixed 5 overly-broad regex patterns that could silently match the wrong
  raw vendor key, found by testing every pattern against every real key
  from an actual Alpine mylonite dataset (Acquisition_settings_XRE.txt,
  scan_settings.txt, data_set_settings.ini):
    1. height/width patterns matched sample "Height (mm)"/"Diameter (mm)"
       instead of detector "Rows"/"Columns".
    2. tube_current_uA pattern could match unrelated "Target current"
       focus-targeting fields instead of the real tube current.
    3. tube_power_W pattern could match the commanded "set value" instead
       of the measured "actual value".
    4. aperture_filter pattern collided with unrelated reconstruction
       filter settings ("Filter type", "Filter level", "Spot filter").
    5. pixel/voxel size catch-all pattern conflated raw detector pixel
       pitch with final reconstructed voxel size; removed the broad
       catch-all and kept only the already-correct anchored Voxel size
       rule plus a new anchored pixel-size-in-mm rule.
"""

from typing import List

# ---------------------------------------------------------------------------
# Field lists
# ---------------------------------------------------------------------------

EXCITE_ACQ_KEYS: List[str] = [
    "source_object_distance_mm",
    "object_detector_distance_mm",
    "source_detector_distance_mm",
    "optical_magnification",
    "tube_voltage_kV",
    "tube_power_W",
    "tube_current_uA",
    "aperture_filter",
    "aperture_filter_material",
    "aperture_filter_thickness_mm",
    "time_per_exposure_s",
    "exposures_per_projection",
    "scanning_trajectory",
    "scanning_mode",
    "total_angular_range_deg",
    "total_num_projections",
    "total_acquisition_time_s",
    "projection_image_height_px",
    "projection_image_width_px",
    "projection_image_bit_depth",
    "projection_image_pixel_size_um",
    "acquisition_software",
]

EXCITE_REC_KEYS: List[str] = [
    "recsoftware_id",
    "reconstruction_software",
    "reconstruction_algorithm",
    "filter",
    "center_shift",
    "beam_hardening_correction_algorithm",
    "rotation_angle",
    "grey_level",
    "rotation_mode",
]

EXCITE_EXTENDED_KEYS: List[str] = [
    "sample_id", "project_name", "application_domain", "data_owner",
    "contact_person", "operator_name", "notes",
    "scan_identifier", "scan_label", "batch_id",
    "instrument_model", "instrument_name", "instrument_serial_number",
    "software_version", "xray_tube_name", "sample_diameter_mm",
    "acquisition_start_time", "acquisition_end_time",
    "status_success", "status_error",
]

# Merged, deduplicated master list — used by the AI embedding fallback
CANONICAL_FIELDS: List[str] = list(dict.fromkeys(
    EXCITE_ACQ_KEYS + EXCITE_REC_KEYS + EXCITE_EXTENDED_KEYS
))

# ---------------------------------------------------------------------------
# Vendor-key → canonical-key regex mappings
# ---------------------------------------------------------------------------
# Each key is a regex pattern (re.IGNORECASE applied at match time).
# Each value is the canonical EXCITE field name it maps to.
# Order matters: first match wins.

TERM_SYNONYMS: dict = {
    # --- Geometry ---
    r"\bSOD\b|SrcToObject|Source[-_ ]?Object[-_ ]?Distance|source object distance":   "source_object_distance_mm",
    r"\bODD\b|Object[-_ ]?Detector[-_ ]?Distance|object detector distance":            "object_detector_distance_mm",
    r"\bSDD\b|SrcToDetector|Source[-_ ]?Detector[-_ ]?Distance|source detector distance": "source_detector_distance_mm",
    r"optical magnification|Magnification|objective(?: lens)?|^\s*mag\s*$|^\s*\d+x\s*$": "optical_magnification",

    # --- X-ray source ---
# FIXED (bug 6): was including "kV set value" as an accepted alternative
    # alongside "kV actual value". Since dict order/file order isn't
    # guaranteed, the commanded (set) value could silently win over the
    # real measured value -- same failure shape as bugs 2 and 3 (current,
    # power). Anchored to only the real, measured voltage field names.
    # Bare "Voltage"/"energy" removed: too broad, and "energy" specifically
    # risks colliding with unrelated future keys (confirmed via isolated
    # test, see 01/08 sweep).
    r"^(kV actual value|Tube voltage|tube voltage)$": "tube_voltage_kV",
    # FIXED (bug 3): was r"(Target power actual value|tube power|Target power set value|Tube power|Power|power)"
    # Old pattern could match the commanded "Target power set value" (23.000000)
    # instead of the measured "Target power actual value" (23.019213). Anchored
    # to the two real "actual/measured power" spellings seen across vendor files.
    r"^Target power actual value$|^Tube power$": "tube_power_W",

    # FIXED (bug 2): was r"(Current set value|Current actual value|Target current set value|Target current actual value|XrayuA|current)"
    # Old pattern could match unrelated "Target current set/actual value" fields,
    # which are a DIFFERENT focus-targeting parameter, not tube current at all.
    # Anchored to only the real, measured tube current field.
    r"^Current actual value$": "tube_current_uA",

    # --- Filter ---
    r"(Filter material|FilterMaterial|XrayFilterMaterial|aperture filter material)": "aperture_filter_material",
    r"(Filter thickness|aperture filter thickness|filter thickness)":                "aperture_filter_thickness_mm",

    # FIXED (bug 4): was r"(Filter|Spot filter|Filter type|Noise filter|Filter Type|Filter Parameters|Air filter|aperture filter)"
    # Old pattern collided with unrelated reconstruction-stage filter settings
    # ("Filter type", "Filter level", "Spot filter" in [CT-parameters IN]),
    # which describe image-processing filters, not the physical X-ray beam
    # aperture filter. Anchored to only the real aperture filter field names.
    r"^Filter$|^Air filter$|^aperture filter$": "aperture_filter",

    # --- Exposure ---
    r"^Exposure time \(ms\)$":                        "time_per_exposure_ms",
    r"^(Exposure time|time per exposure)$":           "time_per_exposure_s",
    r"(averages)":                                                                   "exposures_per_projection",

    # --- Scan geometry ---
    r"(Projections per 360|projs_per_360)":                                          "total_num_projections",
    r"(Total projections|number projections|import projections|n\.? projections|total num projections)": "total_num_projections",
    # "Duration" (HH:MM:SS, e.g. "00:35:31") is the precise, second-accurate
    # source. "SCAN DURATION" / "total scan time" (e.g. "36 minutes") is a
    # human-rounded approximation from a different vendor file. Keep them
    # as separate canonical fields so the precise one always wins, instead
    # of depending on file processing order.
    r"^(time per 360 rotation|Duration)$":                                           "total_acquisition_time_s",
    r"^(SCAN DURATION|total scan time)$":                                            "total_acquisition_time_approx_s",
    r"(scanning mode|imaging mode)":                                                 "scanning_mode",
    r"^Mode$":                                                                       "scanning_mode",
    r"(trajectory|scanning trajectory)":                                             "scanning_trajectory",
    r"(angular range|total angular range|CT stop angle)":                            "total_angular_range_deg",
    # --- Detector / image ---
    r"^(image size|ImageSize)$":                                                     "projection_image_width_height_px",
    # "Voxel size" key: unit handling (mm vs um) is now resolved
    # content-based, inside the normaliser (_parse_voxel_size_um),
    # instead of depending on which file the key came from.
    r"^Voxel size$":                                                                 "projection_image_voxel_size_um",

    # FIXED (bug 5): removed the old broad catch-all
    #   r"(Voxel size|VoxelSize|Pixel size|VoxelSizeX|VoxelSizeY|VoxelSizeZ|projection image pixel size|pixel size)": "projection_image_pixel_size_um"
    # It conflated raw detector pixel pitch ("Pixel size", 0.150000mm) with
    # the final reconstructed voxel size ("Voxel size", 0.023000mm), two
    # genuinely different physical quantities. The anchored "Voxel size"
    # rule directly above already handles voxel size correctly on its own.
    # Raw detector pixel pitch is now captured separately, in mm, below.
    r"^(Unbinned pixelsize \(mm\)|Binned pixelsize \(mm\))$":                        "projection_image_pixel_size_mm",

    r"(bit depth|bits per pixel|bpp|projection image bit depth)":                    "projection_image_bit_depth",

    # FIXED (bug 1): was r"(width|image width|projection image width)"
    #                and r"(height|image height|projection image height)"
    # Old unanchored patterns matched the SAMPLE'S physical "Diameter (mm)"
    # and "Height (mm)" fields (substring "height" inside "Height (mm)"),
    # instead of the real detector dimensions "Columns"/"Rows". Confirmed:
    # sample Height (mm) = 8.904707, real detector Rows = 2856, Columns = 2856.
    r"^(width|image width|projection image width|columns)$":                        "projection_image_width_px",
    r"^(height|image height|projection image height|rows)$":                        "projection_image_height_px",

    # --- Software ---
    r"(acquisition software|instrument software|software version|XRMReconstructor)": "acquisition_software",
 
    # --- Reconstruction ---
    r"(recsoftware ID|reconstruction software id|reconstructor .*|ZEISS .* version.*)": "recsoftware_id",
    r"(reconstruction software|reconstructor)":                                      "reconstruction_software",
    r"^reconstruction algorithm$":                                                    "reconstruction_algorithm",    r"^Filter type$":                                                                "filter",
    r"(center shift|\bCOR\b|correction of center shift|AutomaticCentreOfRotation|Centre of rotation)": "center_shift",
    r"(beam hardening correction|bhc|Beam hardening correction method)":             "beam_hardening_correction_algorithm",
    r"(rotation angle|InitialAngle|Start angle|Last angle|Offset angle)":            "rotation_angle",
    r"^Rotation mode$":                                                              "rotation_mode",
    r"(grey level|gray|ScalingMinimum|ScalingMaximum|Min grey value|Max grey value)": "grey_level",

    # --- Admin / general ---
    r"^sample\s*name$":                   "sample_id",
    r"^project(\s*name)?$":               "project_name",
    r"^application\s*area$":              "application_domain",
    r"^owner$":                           "data_owner",
    r"^contact\s*person$":                "contact_person",
    r"^operator$":                        "operator_name",
    r"^comment$":                         "notes",

    # --- Scan identifiers ---
    r"^scan\s*id$|^scanid$":              "scan_identifier",
    r"^scan\s*name$":                     "scan_label",
    r"^batchid$":                         "batch_id",

    # --- Instrument ---
    r"^scanner\s*type$":                  "instrument_model",
    r"^scanner\s*name$":                  "instrument_name",
    r"^scanner\s*(s/?n|serial)$":         "instrument_serial_number",
    r"^acquila\s*version$|^acquila$":     "software_version",
    r"^tube\s*name$":                     "xray_tube_name",
    r"^diameter\s*\(mm\)$":              "sample_diameter_mm",

    # --- Timing / status ---
    r"^start$|^acq(uisition)?\s*start$":  "acquisition_start_time",
    r"^stop$|^acq(uisition)?\s*end$":     "acquisition_end_time",
    r"^succeeded$":                        "status_success",
    r"^error$":                            "status_error",
}
