"""
parsers.py
----------
Responsible for:
  - Finding candidate metadata files in a dataset folder
  - Parsing .txt / .log / .ini / .cfg / .xml / .csv files into raw key-value dicts
  - Merging all sources into one flat dict with provenance tracking

No schema knowledge lives here — this module just harvests raw key-value pairs
from whatever files it finds.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_metadata_files(root: Path) -> List[Path]:
    """
    Recursively find all candidate metadata files under *root*.

    Accepted by extension : .txt  .log  .ini  .cfg  .xml  .csv
    Accepted by suffix    : .acq.1  .scan  .vis.1  (vendor-specific, not yet .xml)
    Size limit            : < 20 MB  (avoids accidentally parsing image data)
    """
    exts = {".txt", ".log", ".ini", ".cfg", ".xml", ".csv"}
    vendor_suffixes = (".acq.1", ".scan", ".vis.1")
    candidates = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        ok_ext = p.suffix.lower() in exts
        ok_vendor = any(str(p).lower().endswith(s) for s in vendor_suffixes)
        if (ok_ext or ok_vendor) and p.stat().st_size < 20_000_000:
            candidates.append(p)
    return candidates


# ---------------------------------------------------------------------------
# Individual file parsers
# ---------------------------------------------------------------------------

def collect_text_pairs(text: str) -> Dict[str, Any]:
    """
    Parse a block of text where each line is  key: value  or  key = value.
    Returns a dict of stripped string pairs.
    """
    pairs: Dict[str, Any] = {}
    for line in text.splitlines():
        if ":" in line or "=" in line:
            k, v = re.split(r"[:=]", line, maxsplit=1)
            k, v = k.strip(), v.strip()
            if k and v:
                pairs[k] = v
    return pairs


def parse_txt_file(path: Path) -> Dict[str, Any]:
    """Parse a plain-text or .log file as key-value pairs."""
    try:
        return collect_text_pairs(path.read_text(errors="ignore"))
    except Exception:
        return {}


def parse_xml_file(path: Path) -> Dict[str, Any]:
    """
    Parse an XML file by iterating all elements.
    - Element text  → stored as  tag: text
    - Attributes    → stored as  tag.attr: value
    """
    out: Dict[str, Any] = {}
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag.split("}")[-1]   # strip XML namespace
            if elem.text and elem.text.strip():
                out[tag] = elem.text.strip()
            for ak, av in elem.attrib.items():
                out[f"{tag}.{ak}"] = av
    except Exception:
        pass
    return out


def parse_ini_file(path: Path) -> Dict[str, Any]:
    """Parse .ini / .cfg files (reuses the text key-value parser)."""
    return parse_txt_file(path)

def _is_binary(path: Path, chunk_size: int = 8192) -> bool:
    """
    Detect whether a file is binary rather than genuine text, regardless
    of its extension or filename. Files that claim a .txt/.log extension
    but actually contain binary data (e.g. raw hardware logs) produce
    garbled, meaningless keys if parsed as text. A null byte in the
    first chunk of the file is a standard, reliable signal of binary
    content -- genuine text files essentially never contain one.
    """
    try:
        with open(path, "rb") as f:
            chunk = f.read(chunk_size)
        return b"\x00" in chunk
    except Exception:
        return False
    
def _precision_score(value: Any) -> int:
    """
    Count the significant figures in a numeric-looking string, used to
    decide which of two duplicate raw-key values (from different files)
    is more precise. Leading zeros (e.g. the "0" in "0.023") and
    trailing zeros (e.g. the padding zeros in "0.023000") are not
    counted, since they don't represent genuine measured precision.
    Returns -1 for values with no digits at all, so they never win
    against a real numeric value.
    """
    if value is None:
        return -1
    s = str(value).strip().strip('"').strip("'")
    match = re.search(r"-?\d[\d.]*\d|-?\d", s)
    if not match:
        return -1
    digits_only = match.group(0).replace("-", "").replace(".", "")
    digits_only = digits_only.lstrip("0").rstrip("0")
    return len(digits_only)

# ---------------------------------------------------------------------------
# Harvester — merges all files with provenance
# ---------------------------------------------------------------------------

def harvest_pairs(paths: List[Path]) -> Tuple[Dict[str, Any], Dict[str, List[str]]]:
    """
    Parse every file in *paths* and merge results into one flat dict.

    Returns
    -------
    merged   : {raw_key: value}   — last-write wins per key across files,
               UNLESS an earlier value is more precise (more significant
               figures), in which case the more precise value is kept
    provenance: {raw_key: [file_path, ...]}  — every file that supplied the key
    """
    merged: Dict[str, Any] = {}
    provenance: Dict[str, List[str]] = {}

    for p in paths:
        ext = p.suffix.lower()
        if ext in {".txt", ".log"}:
            if _is_binary(p):
                data = {}
            else:
                data = parse_txt_file(p)
        elif ext == ".xml":
            data = parse_xml_file(p)
        elif ext in {".ini", ".cfg"}:
            data = parse_ini_file(p)
        elif ext == ".csv":
            try:
                head = p.read_text(errors="ignore").splitlines()[:2]
                data = collect_text_pairs("\n".join(head))
            except Exception:
                data = {}
        else:
            data = {}

        for k, v in data.items():
            if k in merged and _precision_score(v) < _precision_score(merged[k]):
                # A value already stored for this key is more precise
                # (more significant figures) than the new one -- keep
                # the existing value, even though plain "last write
                # wins" would normally overwrite it. This makes the
                # result deterministic regardless of file processing
                # order, rather than depending on which file happens
                # to be read last. Provenance still records every file
                # that supplied the key, either way.
                provenance.setdefault(k, []).append(str(p))
                continue
            merged[k] = v
            provenance.setdefault(k, []).append(str(p))

    return merged, provenance
