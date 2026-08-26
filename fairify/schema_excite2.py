"""
schema_excite2.py
------------------
Metadata schema aligned to the EXCITE2 network's own graph data model
(Deliverable D4.2, Appendix I), not a CT-physics-only schema.

NODES: Sample, Site, Operator, Instrument, Software, License, Data & metadata
EDGES: Sampling, Sample processing, Measuring

This REPLACES the previous excite_ct_schema_v1.json approach. The previous
schema only modelled CT acquisition physics (kV, current, voxel size...).
This schema models the full EXCITE2 graph, so it can be checked against the
network's own required/recommended/optional tiers, not just a CT-specific
ad hoc list.

Every field below carries:
    tier        : "required" | "recommended" | "optional"   (per Appendix I)
    extractable : True  -> a regex pattern exists and a real source key was
                            confirmed present in at least one Alpine mylonite
                            vendor file during the field-by-field audit
                  False -> structurally absent from CT scanner log files;
                            no instrument log can ever answer this; left
                            permanently null unless a second input channel
                            (manual entry / external registry) is added later
    pattern     : the regex used to recognise this field from a raw vendor key
                  (None if extractable is False -- there is nothing to match)

Goal of this file, right now: EXTRACTION ONLY. For every field, try the
pattern against the raw vendor keys. If it matches, fill the value. If it
does not match (or extractable is False), the value stays null. No manual
entry, no forms, no second channel -- that is explicitly out of scope here.
"""

from typing import Dict, Any, List

# ---------------------------------------------------------------------------
# NODE: Sample
# ---------------------------------------------------------------------------
SAMPLE_FIELDS: Dict[str, Dict[str, Any]] = {
    "igsn_id": {
        "tier": "required",
        "extractable": False,
        "pattern": None,
        "note": "External registry ID (International Generic Sample Number). "
                "Never present in a CT scanner log; must be assigned externally.",
    },
    "sample_id": {
        "tier": "recommended",
        "extractable": True,
        "pattern": r"^sample\s*name$",
        "note": "Confirmed present as 'Sample name' in Alpine mylonite files "
                "(value: 'Alpine mylonite').",
    },
    "other_sample_id": {
        "tier": "optional",
        "extractable": False,
        "pattern": None,
        "note": "No alternate/field naming convention logged by scanner software.",
    },
    "availability": {
        "tier": "optional",
        "extractable": False,
        "pattern": None,
        "note": "IGSN public/private flag. Not a scanner concept.",
    },
    "parent_sample": {
        "tier": "recommended",
        "extractable": False,
        "pattern": None,
        "note": "Sub-sampling lineage. Not logged; would require a sample registry.",
    },
    "origin_site_link": {
        "tier": "recommended",
        "extractable": False,
        "pattern": None,
        "note": "Link to Site node. No geographic field exists in any CT log file.",
    },
    "type": {
        "tier": "required",
        "extractable": False,
        "pattern": None,
        "note": "Type of sample (e.g. core, thin section, powder). The scanner "
                "logs a free-text sample NAME, never a formal type classification.",
    },
    "dimensions": {
        "tier": "recommended",
        "extractable": True,
        "pattern": r"^diameter\s*\(mm\)$|^sample\s*size$|^height\s*\(mm\)$",
        "unit_from_key": True,
        "note": "CORRECTED: previously returned a bare number, discarding "
                "the unit that is only present in the KEY name itself "
                "(e.g. 'Diameter (mm)'). Now returns {value, unit, "
                "dimension_type} so the unit is never silently lost. "
                "'dimension_type' records which raw key matched (diameter, "
                "sample size, or height), since these are different "
                "physical measurements, not interchangeable.",
    },
    "material": {
        "tier": "required",
        "extractable": False,
        "pattern": None,
        "note": "Required field per spec, but 'Alpine mylonite' as logged is a "
                "rock NAME, not a material classification (e.g. 'rock', "
                "'mineral'). Classifying it correctly needs geological "
                "judgement the scanner does not have.",
    },
    "intrinsic_descriptors": {
        "tier": "optional",
        "extractable": False,
        "pattern": None,
        "note": "Controlled-list classification specific to rock/mineral/bio. "
                "Not present.",
    },
    "description": {
        "tier": "optional",
        "extractable": True,
        "pattern": r"^comment$",
        "note": "'Comment' field exists in the source file structure but was "
                "empty for this particular run.",
    },
    "processing_link": {
        "tier": "optional",
        "extractable": False,
        "pattern": None,
        "note": "Self-link to processing steps undergone by the sample. Not present.",
    },
}

# ---------------------------------------------------------------------------
# NODE: Site (geographic origin)
# ---------------------------------------------------------------------------
SITE_FIELDS: Dict[str, Dict[str, Any]] = {
    "latitude": {
        "tier": "optional", "extractable": False, "pattern": None,
        "note": "No geographic field anywhere in CT acquisition logs.",
    },
    "longitude": {
        "tier": "optional", "extractable": False, "pattern": None,
        "note": "Same as latitude.",
    },
    "coordinate_system": {
        "tier": "optional", "extractable": False, "pattern": None,
        "note": "Same.",
    },
    "vertical_datum": {
        "tier": "optional", "extractable": False, "pattern": None,
        "note": "Same.",
    },
    "location": {
        "tier": "optional", "extractable": False, "pattern": None,
        "note": "Geographic name of sampling location. Not present.",
    },
    "country": {
        "tier": "optional", "extractable": False, "pattern": None,
        "note": "Not present.",
    },
}

# ---------------------------------------------------------------------------
# NODE: Operator
# ---------------------------------------------------------------------------
OPERATOR_FIELDS: Dict[str, Dict[str, Any]] = {
    "person_id": {
        "tier": "recommended", "extractable": False, "pattern": None,
        "note": "No formal technician/researcher ID system in scanner software.",
    },
    "name": {
        "tier": "required",
        "extractable": True,
        "pattern": r"^owner$",
        "note": "CORRECTED: previously matched 'Operator' and returned "
                "'admin', a login name. The raw files actually contain TWO "
                "distinct people: 'Operator' (login that ran the scan, e.g. "
                "'admin') and 'Owner' (the real person, e.g. 'Peter'). For "
                "the EXCITE2 'Name' field, which is meant to identify the "
                "responsible person, 'Owner' is the correct source. "
                "'Operator' is preserved separately below as operator_login, "
                "since it is real information that should not be discarded, "
                "it just is not what EXCITE2's 'Name' field is asking for.",
    },
    "operator_login": {
        "tier": "not_in_excite2_spec",
        "extractable": True,
        "pattern": r"^operator$",
        "note": "Not an official EXCITE2 Appendix I field. Kept anyway "
                "because 'admin' is real, useful operational information "
                "(which account ran the scan) that would otherwise be "
                "silently discarded now that 'name' correctly points to "
                "Owner instead.",
    },
    "email": {
        "tier": "required",
        "extractable": False,
        "pattern": None,
        "note": "Never logged by CT scanner software.",
    },
}

# ---------------------------------------------------------------------------
# NODE: Instrument
# ---------------------------------------------------------------------------
INSTRUMENT_FIELDS: Dict[str, Dict[str, Any]] = {
    "instrument_id": {
        "tier": "required", "extractable": False, "pattern": None,
        "note": "No formal instrument registry ID logged. 'scanID' in the "
                "source file identifies the SCAN, not the instrument itself.",
    },
    "instrument_type": {
        "tier": "required",
        "extractable": True,
        "pattern": None,
        "constant_value": "X-ray CT scanner",
        "note": "CORRECTED after testing: the 'Scanner type' raw key holds the "
                "MODEL ('UniTOM XL'), not a type classification. The type is "
                "asserted as a constant since this pipeline is CT-specific by "
                "definition, the same approach used for measuring.technique. "
                "A regex against 'Scanner type' would wrongly return the "
                "model name here, which is what instrument_model is for.",
    },
    "manufacturer": {
        "tier": "recommended", "extractable": False, "pattern": None,
        "note": "Not present in any field. 'UniTOM XL' is the model line; "
                "manufacturer name is not separately logged.",
    },
    "instrument_model": {
        "tier": "recommended",
        "extractable": True,
        "pattern": r"^scanner\s*type$",
        "note": "Confirmed present, value 'UniTOM XL'.",
    },
    "serial": {
        "tier": "recommended",
        "extractable": True,
        "pattern": r"^scanner\s*(s/?n|serial)$|^serialnumber$",
        "note": "Confirmed present as 'scanner S/N' / 'SerialNumber', "
                "value '121-0107'.",
    },
    "mode": {
        "tier": "optional",
        "extractable": True,
        "pattern": r"^vertical\s*mode$",
        "note": "CORRECTED after real-data test: the original pattern "
                "(r'imaging mode|vertical mode') was matching an unrelated "
                "key holding a scanning-mode code ('1_HW1SW1LOW') instead "
                "of the intended 'Vertical mode' value ('Cone beam'). "
                "Tightened to match only 'Vertical mode' exactly. If your "
                "vendor file uses a different key for imaging mode, this "
                "field will now correctly return null rather than a wrong "
                "value, which is preferable.",
    },
}

# ---------------------------------------------------------------------------
# NODE: Software
# ---------------------------------------------------------------------------
SOFTWARE_FIELDS: Dict[str, Dict[str, Any]] = {
    "software_id": {
        "tier": "required", "extractable": False, "pattern": None,
        "note": "No unique software identifier logged.",
    },
    "software_category": {
        "tier": "required", "extractable": False, "pattern": None,
        "note": "Not present. Would need to be inferred/asserted as "
                "'acquisition software' rather than read from the file.",
    },
    "distributor": {
        "tier": "recommended", "extractable": False, "pattern": None,
        "note": "Not present.",
    },
    "name": {
        "tier": "recommended",
        "extractable": False,
        "pattern": None,
        "note": "CORRECTED after testing: the 'Acquila version' raw key's "
                "VALUE is a version string ('4146:ef16e0a4e6f3'), not the "
                "software name. 'Acquila' is only known because it appears "
                "in the KEY NAME itself, not in any value our extractor "
                "reads. A real fix would need to special-case 'parse the "
                "name out of this specific key's name string', which is "
                "fragile and vendor-specific; marking honestly as not "
                "extractable by the current generic key/value pattern "
                "matching approach.",
    },
    "version": {
        "tier": "recommended",
        "extractable": True,
        "pattern": r"^acquila\s*version$",
        "note": "Confirmed present in the same field as the name.",
    },
}

# ---------------------------------------------------------------------------
# NODE: License
# ---------------------------------------------------------------------------
LICENSE_FIELDS: Dict[str, Dict[str, Any]] = {
    "license_type": {
        "tier": "required", "extractable": False, "pattern": None,
        "note": "Never present in acquisition-time files. This is a "
                "deposit-time decision, not instrument output.",
    },
}

# ---------------------------------------------------------------------------
# EDGE: Sampling  (site -> sample)
# ---------------------------------------------------------------------------
SAMPLING_EDGE_FIELDS: Dict[str, Dict[str, Any]] = {
    "technique": {
        "tier": "required", "extractable": False, "pattern": None,
        "note": "How the rock was physically collected in the field. Happens "
                "before the sample ever reaches the CT facility; cannot be "
                "in a scanner log.",
    },
    "instrument": {
        "tier": "optional", "extractable": False, "pattern": None,
        "note": "Field-collection tool (e.g. coring rig), not the CT scanner.",
    },
    "parameters": {
        "tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning.",
    },
    "operator": {
        "tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning.",
    },
    "date_time": {
        "tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning.",
    },
    "observations": {
        "tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning.",
    },
}

# ---------------------------------------------------------------------------
# EDGE: Sample processing  (sample -> sample, e.g. cutting/mounting)
# ---------------------------------------------------------------------------
SAMPLE_PROCESSING_EDGE_FIELDS: Dict[str, Dict[str, Any]] = {
    "technique": {
        "tier": "required", "extractable": False, "pattern": None,
        "note": "Cutting/polishing/mounting prep, done in a lab before "
                "scanning, never logged by the CT instrument.",
    },
    "instrument": {"tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning."},
    "parameters": {"tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning."},
    "operator": {"tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning."},
    "date_time": {"tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning."},
    "observations": {"tier": "optional", "extractable": False, "pattern": None, "note": "Same reasoning."},
}

# ---------------------------------------------------------------------------
# EDGE: Measuring  (instrument + sample -> data)
# This is the one edge CT acquisition logs are actually designed to record.
# ---------------------------------------------------------------------------
MEASURING_EDGE_FIELDS: Dict[str, Dict[str, Any]] = {
    "technique": {
        "tier": "required",
        "extractable": True,
        "pattern": None,  # asserted constant, not regex-matched
        "constant_value": "X-ray computed tomography",
        "note": "Not matched from a vendor key; asserted as a constant since "
                "this pipeline is CT-specific by definition.",
    },
    "instrument": {
        "tier": "optional",
        "extractable": True,
        "pattern": r"^scanner\s*type$",
        "note": "Same source as instrument_model above.",
    },
    "parameters": {
        "tier": "optional",
        "extractable": True,
        "pattern": None,
        "note": "This is exactly the existing CT acquisition block (kV, "
                "current, voxel size, exposure, distances...). Already "
                "well covered by the original excite_ct_schema_v1.json work; "
                "reuse that extraction logic unchanged here.",
    },
    "operator": {
        "tier": "optional",
        "extractable": True,
        "pattern": r"^operator$",
        "note": "Same caveat as Operator.name above: value is 'admin', "
                "technically present but low quality.",
    },
    "date_time": {
        "tier": "optional",
        "extractable": True,
        "pattern": r"^start$|^stop$",
        "note": "Confirmed present as 'Start' / 'Stop' timestamps.",
    },
    "facility": {
        "tier": "required",
        "extractable": True,
        "pattern": r"^project(\s*name)?$",
        "note": "Confirmed present as 'Project' field, value 'EXcite', used "
                "as a proxy for the EXCITE facility where acquisition "
                "took place.",
    },
}

# ---------------------------------------------------------------------------
# Aggregate view -- useful for the audit report / completeness scoring
# ---------------------------------------------------------------------------
ALL_NODES_AND_EDGES = {
    "sample": SAMPLE_FIELDS,
    "site": SITE_FIELDS,
    "operator": OPERATOR_FIELDS,
    "instrument": INSTRUMENT_FIELDS,
    "software": SOFTWARE_FIELDS,
    "license": LICENSE_FIELDS,
    "sampling_edge": SAMPLING_EDGE_FIELDS,
    "sample_processing_edge": SAMPLE_PROCESSING_EDGE_FIELDS,
    "measuring_edge": MEASURING_EDGE_FIELDS,
}


def extraction_coverage_report() -> Dict[str, Dict[str, Any]]:
    """
    For each node/edge, count how many fields are extractable vs not,
    broken down by tier. This is the machine-readable version of the
    audit table built by hand earlier.
    """
    report = {}
    for group_name, fields in ALL_NODES_AND_EDGES.items():
        official_fields = {n: f for n, f in fields.items() if f["tier"] != "not_in_excite2_spec"}
        bonus_fields = {n: f for n, f in fields.items() if f["tier"] == "not_in_excite2_spec"}

        total = len(official_fields)
        extractable = sum(1 for f in official_fields.values() if f["extractable"])
        required_total = sum(1 for f in official_fields.values() if f["tier"] == "required")
        required_extractable = sum(
            1 for f in official_fields.values() if f["tier"] == "required" and f["extractable"]
        )
        report[group_name] = {
            "total_fields": total,
            "extractable_fields": extractable,
            "coverage_percent": round(100 * extractable / total, 1) if total else 0.0,
            "required_fields": required_total,
            "required_fields_extractable": required_extractable,
            "required_coverage_percent": (
                round(100 * required_extractable / required_total, 1)
                if required_total else 100.0
            ),
            "bonus_fields_not_in_spec": list(bonus_fields.keys()),
        }
    return report


if __name__ == "__main__":
    import json
    print(json.dumps(extraction_coverage_report(), indent=2))
