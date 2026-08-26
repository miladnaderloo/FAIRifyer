"""
validator.py
------------
Validates the conceptual_metadata block produced by the FAIRifyer pipeline
against the EXCITE CT JSON Schema (excite_ct_schema_v1.json).

Uses jsonschema Draft7Validator — the same library already used in the
prototype notebook, so nothing new needs to be installed.

Public API
----------
    from fairify.validator import validate_conceptual, ValidationReport

    report = validate_conceptual(structured["conceptual_metadata"])
    print(report.completeness_percent)
    structured["validation"] = report.to_dict()
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft7Validator

# Path to the schema file — lives in schemas/ next to the package
_SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "excite_ct_schema_v1.json"


def _load_schema() -> Dict[str, Any]:
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Schema file not found: {_SCHEMA_PATH}\n"
            "Make sure schemas/excite_ct_schema_v1.json exists in your project folder."
        )
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))

#second schema
_SCHEMA_EXCITE2_PATH = Path(__file__).parent.parent / "schemas" / "excite2_graph_schema_v1.json"

def _load_excite2_schema() -> Dict[str, Any]:
    if not _SCHEMA_EXCITE2_PATH.exists():
        raise FileNotFoundError(
            f"Schema file not found: {_SCHEMA_EXCITE2_PATH}\n"
            "Make sure schemas/excite2_graph_schema_v1.json exists in your project folder."
        )
    return json.loads(_SCHEMA_EXCITE2_PATH.read_text(encoding="utf-8"))

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class FieldIssue:
    """One validation issue on one field."""
    field: str          # dot-path, e.g. "reconstruction.grey_level"
    message: str        # human-readable explanation
    issue_type: str     # "missing_required" | "wrong_type" | "out_of_range" | "other"


@dataclass
class ValidationReport:
    """
    Full validation result for one metadata record.

    Attributes
    ----------
    required_total    : how many required fields the schema defines
    required_present  : how many of those are present and non-null
    required_missing  : list of required field names that are absent
    issues            : all validation issues found (type errors, range errors…)
    completeness_percent : required_present / required_total * 100
    overall_pass      : True only when zero issues and zero missing required fields
    """
    required_total:    int
    required_present:  int
    required_missing:  List[str]
    issues:            List[FieldIssue] = field(default_factory=list)

    @property
    def completeness_percent(self) -> float:
        if self.required_total == 0:
            return 100.0
        return round(self.required_present / self.required_total * 100, 1)

    @property
    def overall_pass(self) -> bool:
        return len(self.issues) == 0 and len(self.required_missing) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to plain dict for embedding in the output JSON."""
        return {
            "overall_pass": self.overall_pass,
            "completeness_percent": self.completeness_percent,
            "summary": {
                "required_total":   self.required_total,
                "required_present": self.required_present,
                "required_missing": self.required_missing,
                "total_issues":     len(self.issues),
            },
            "issues": [
                {
                    "field":      i.field,
                    "message":    i.message,
                    "issue_type": i.issue_type,
                }
                for i in self.issues
            ],
        }

    def print_report(self) -> None:
        """Human-readable console summary."""
        status = "✅  PASS" if self.overall_pass else "❌  FAIL"
        print(f"\n{'='*60}")
        print(f"  EXCITE VALIDATION REPORT  —  {status}")
        print(f"{'='*60}")
        print(f"  Completeness : {self.completeness_percent}%  "
              f"({self.required_present} / {self.required_total} required fields)")

        if self.required_missing:
            print(f"\n  ⚠  REQUIRED FIELDS MISSING ({len(self.required_missing)}):")
            for f in self.required_missing:
                print(f"       • {f}")

        if self.issues:
            print(f"\n  ✗  ISSUES FOUND ({len(self.issues)}):")
            for issue in self.issues:
                print(f"       [{issue.field}] {issue.message}")

        print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------

def _field_path(error_path) -> str:
    """Convert a jsonschema error path deque to a readable dot-string."""
    parts = list(error_path)
    return ".".join(str(p) for p in parts) if parts else "(root)"


def _classify(error) -> str:
    """Map a jsonschema error validator name to a simple issue_type string."""
    mapping = {
        "required": "missing_required",
        "type":     "wrong_type",
        "minimum":  "out_of_range",
        "maximum":  "out_of_range",
        "enum":     "invalid_value",
    }
    return mapping.get(error.validator, "other")


def validate_conceptual(
    conceptual_metadata: Dict[str, Any],
    schema: Dict[str, Any] | None = None,
) -> ValidationReport:
    """
    Validate a conceptual_metadata dict against the EXCITE JSON Schema.

    Parameters
    ----------
    conceptual_metadata : the dict at structured["conceptual_metadata"]
    schema              : optional pre-loaded schema dict (loads from file if None)

    Returns
    -------
    ValidationReport
    """
    if schema is None:
        schema = _load_schema()

    validator = Draft7Validator(schema)

    # --- Collect all jsonschema errors ---
    issues: List[FieldIssue] = []
    for error in sorted(validator.iter_errors(conceptual_metadata), key=lambda e: list(e.path)):
        if error.validator == "required":
            # jsonschema reports missing required as a root-level error
            # with the field name embedded in the message
            missing_field = error.message.split("'")[1] if "'" in error.message else error.message
            issues.append(FieldIssue(
                field=missing_field,
                message=f"Required field '{missing_field}' is missing.",
                issue_type="missing_required",
            ))
        else:
            issues.append(FieldIssue(
                field=_field_path(error.path),
                message=error.message,
                issue_type=_classify(error),
            ))

    # --- Completeness score ---
    # Walk all required fields defined in the schema
    required_fields = schema.get("required", [])

    # Also count required fields inside nested objects (e.g. reconstruction)
    nested_required: List[str] = []
    for prop_name, prop_def in schema.get("properties", {}).items():
        if isinstance(prop_def, dict) and "required" in prop_def:
            for sub in prop_def["required"]:
                nested_required.append(f"{prop_name}.{sub}")

    all_required = required_fields + nested_required
    required_total = len(all_required)

    def _get_nested(d: Dict, dotpath: str) -> Any:
        """Retrieve a value from a nested dict using a dot-path string."""
        keys = dotpath.split(".")
        val = d
        for k in keys:
            if not isinstance(val, dict):
                return None
            val = val.get(k)
        return val

    required_missing = [
        f for f in all_required
        if _get_nested(conceptual_metadata, f) is None
    ]
    required_present = required_total - len(required_missing)

    return ValidationReport(
        required_total=required_total,
        required_present=required_present,
        required_missing=required_missing,
        issues=issues,
    )


# ADDED SECTION=
def _collect_required_paths(schema_node: Dict[str, Any], prefix: str = "") -> List[str]:
    """
    Recursively collect the full dot-path of every required field in a
    JSON Schema, at any depth of nesting. Needed because
    excite2_graph_schema_v1.json nests three levels deep
    (root -> nodes/edges -> node/edge -> field), unlike
    excite_ct_schema_v1.json's single level of nesting.
    """
    paths: List[str] = []
    for name in schema_node.get("required", []):
        paths.append(f"{prefix}{name}")
    for prop_name, prop_def in schema_node.get("properties", {}).items():
        if isinstance(prop_def, dict) and "properties" in prop_def:
            paths.extend(_collect_required_paths(prop_def, prefix=f"{prefix}{prop_name}."))
    return paths


def validate_excite2(
    excite2_record: Dict[str, Any],
    schema: Dict[str, Any] | None = None,
) -> ValidationReport:
    """
    Validate a Pipeline 2 (graph-structured) metadata record against the
    EXCITE2 JSON Schema. Mirrors validate_conceptual(), but walks required
    fields recursively since this schema nests deeper.

    Parameters
    ----------
    excite2_record : the dict with "nodes" and "edges" keys, as produced
                      by build_excite2_record()
    schema         : optional pre-loaded schema dict (loads from file if None)

    Returns
    -------
    ValidationReport
    """
    if schema is None:
        schema = _load_excite2_schema()

    validator = Draft7Validator(schema)

    issues: List[FieldIssue] = []
    for error in sorted(validator.iter_errors(excite2_record), key=lambda e: list(e.path)):
        if error.validator == "required":
            missing_field = error.message.split("'")[1] if "'" in error.message else error.message
            issues.append(FieldIssue(
                field=missing_field,
                message=f"Required field '{missing_field}' is missing.",
                issue_type="missing_required",
            ))
        else:
            issues.append(FieldIssue(
                field=_field_path(error.path),
                message=error.message,
                issue_type=_classify(error),
            ))

    all_required = _collect_required_paths(schema)
    required_total = len(all_required)

    def _get_nested(d: Dict, dotpath: str) -> Any:
        keys = dotpath.split(".")
        val = d
        for k in keys:
            if not isinstance(val, dict):
                return None
            val = val.get(k)
        return val

    required_missing = [
        f for f in all_required
        if _get_nested(excite2_record, f) is None
    ]
    required_present = required_total - len(required_missing)

    return ValidationReport(
        required_total=required_total,
        required_present=required_present,
        required_missing=required_missing,
        issues=issues,
    )