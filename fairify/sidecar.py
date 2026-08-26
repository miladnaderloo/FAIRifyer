"""
sidecar.py
----------
Reads a small, manually-filled-in YAML file (one per dataset folder)
that supplies the handful of fields a CT scanner can never record on
its own: Site (where the sample came from), License, and Sample
type/material.

This is a human-filled form, not something extracted from scanner
logs. If the file doesn't exist for a dataset, that's expected and
not an error -- the relevant fields just stay empty.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, Optional

SIDECAR_FILENAME = "metadata_sidecar.yaml"


def read_sidecar(dataset_root: Path) -> Optional[Dict[str, Any]]:
    """
    Look for a sidecar YAML file inside the given dataset folder.

    Returns
    -------
    A dict with the file's contents if the sidecar exists, or None
    if no sidecar file is present for this dataset.
    """
    sidecar_path = dataset_root / SIDECAR_FILENAME
    if not sidecar_path.exists():
        return None

    with open(sidecar_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data

def create_blank_sidecar(dataset_root: Path, overwrite: bool = False) -> Path:
    """
    Create a blank, ready-to-fill-in sidecar YAML file inside a dataset
    folder, with explanatory comments for each field.

    Parameters
    ----------
    dataset_root : the dataset folder to create the sidecar file in
    overwrite     : if False (default), refuses to replace an existing
                    sidecar file, to avoid accidentally erasing values
                    someone already filled in

    Returns
    -------
    The path to the created (or already-existing) sidecar file.
    """
    sidecar_path = dataset_root / SIDECAR_FILENAME

    if sidecar_path.exists() and not overwrite:
        print(f"A sidecar file already exists at {sidecar_path} — "
              f"leaving it untouched. Pass overwrite=True to replace it.")
        return sidecar_path

    template = '''# "site" = where the sample originally came from (geological collection
# location), NOT where it was scanned.
site:
  location: ""
  country: ""

# What kind of sample this is, and what it's made of.
sample:
  type: ""
  material: ""

# The license under which this data is shared, e.g. "CC-BY-4.0".
license:
  license_type: ""

# Contact email for the person responsible for this dataset.
operator:
  email: ""

# Formal registry ID for the instrument, if one exists.
instrument:
  instrument_id: ""

# Formal ID and category for the software used (e.g. "acquisition software").
software:
  software_id: ""
  software_category: ""

# How the sample was physically collected, if applicable.
sampling:
  technique: ""

# How the sample was prepared (cut, polished, mounted) before scanning.
sample_processing:
  technique: ""
'''

    sidecar_path.write_text(template, encoding="utf-8")
    print(f"Created a blank sidecar file at {sidecar_path}")
    return sidecar_path