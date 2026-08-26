"""
translator.py
-------------
Responsible for mapping raw vendor keys → canonical EXCITE field names.

Two-stage hybrid approach:
  1. Regex  — fast, deterministic, covers all known vendor vocabularies
  2. AI     — sentence-transformer embeddings for unknown keys (graceful
              fallback to difflib if the model is not installed)

Imports schema.py for TERM_SYNONYMS and CANONICAL_FIELDS.
No file I/O or unit conversion happens here.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from .schema import CANONICAL_FIELDS, TERM_SYNONYMS

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AI_SIMILARITY_ENABLED: bool = True   # set False to skip AI pass entirely
AI_THRESHOLD: float = 0.82           # minimum cosine similarity to accept a match

# ---------------------------------------------------------------------------
# Optional AI imports — safe if sentence-transformers is not installed
# ---------------------------------------------------------------------------

try:
    import numpy as np
    from sentence_transformers import SentenceTransformer, util as st_util
    _EMBEDDING_AVAILABLE = True
except Exception:
    _EMBEDDING_AVAILABLE = False
    import difflib  # string-similarity fallback

# Lazy-loaded singletons (loaded once on first use, not at import time)
_emb_model: Optional[Any] = None
_canon_emb: Optional[Any] = None


def _get_model() -> Any:
    """Load the sentence embedding model once (lazy singleton)."""
    global _emb_model
    if _emb_model is None:
        _emb_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _emb_model


def _get_canonical_embeddings() -> Optional[Any]:
    """Compute and cache embeddings for all canonical field names."""
    global _canon_emb
    if _canon_emb is None:
        if not _EMBEDDING_AVAILABLE:
            return None
        model = _get_model()
        _canon_emb = model.encode(CANONICAL_FIELDS, normalize_embeddings=True)
    return _canon_emb


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate_terms(
    raw_pairs: Dict[str, Any]
) -> Tuple[Dict[str, Any], Dict[str, float]]:
    """
    Translate raw vendor key-value pairs to canonical EXCITE field names.

    Stage 1 — Regex (TERM_SYNONYMS):
        Every raw key is tested against each regex pattern.
        On a match the key is renamed to its canonical form.
        Score = 1.0 (deterministic).

    Stage 2 — AI embedding (unmapped keys only):
        Keys that survived stage 1 without a match are embedded and compared
        against embeddings of all canonical field names via cosine similarity.
        A match is accepted only when score ≥ AI_THRESHOLD.
        Falls back to difflib.SequenceMatcher if the model is unavailable.

    Parameters
    ----------
    raw_pairs : dict of {vendor_key: value}

    Returns
    -------
    translated  : dict of {canonical_key: value}
                  Unresolved keys are stored under "__unmapped__".
    similarities: dict of {raw_key: score}  — for audit / provenance
    """
    translated: Dict[str, Any] = {}
    similarities: Dict[str, float] = {}

    # ---- Stage 1: regex ----
    for k, v in raw_pairs.items():
        matched = False
        for pattern, canonical in TERM_SYNONYMS.items():
            if re.search(pattern, k, flags=re.IGNORECASE):
                translated.setdefault(canonical, v)
                similarities[k] = 1.0
                matched = True
                break
        if not matched:
            translated.setdefault("__unmapped__", {})[k] = v

    # ---- Stage 2: AI ----
    unmapped: Dict[str, Any] = translated.get("__unmapped__", {})
    if unmapped and AI_SIMILARITY_ENABLED:
        keys: List[str] = list(unmapped.keys())

        if _EMBEDDING_AVAILABLE:
            model = _get_model()
            key_emb  = model.encode(keys,            convert_to_tensor=True, normalize_embeddings=True)
            sch_emb  = model.encode(CANONICAL_FIELDS, convert_to_tensor=True, normalize_embeddings=True)
            cos_scores = st_util.cos_sim(key_emb, sch_emb)

            for i, key in enumerate(keys):
                best_idx   = int(cos_scores[i].argmax())
                best_score = float(cos_scores[i][best_idx])
                best_match = CANONICAL_FIELDS[best_idx]
                similarities[key] = best_score
                if best_score >= AI_THRESHOLD:
                    translated.setdefault(best_match, unmapped[key])
        else:
            # String-similarity fallback (stricter threshold)
            for key, value in unmapped.items():
                best, score = None, 0.0
                for tgt in CANONICAL_FIELDS:
                    s = difflib.SequenceMatcher(a=key.lower(), b=tgt.lower()).ratio()
                    if s > score:
                        best, score = tgt, s
                similarities[key] = score
                if score >= 0.90:
                    translated.setdefault(best, value)

        # Keep only keys that are still below threshold
        translated["__unmapped__"] = {
            k: v for k, v in unmapped.items()
            if similarities.get(k, 0.0) < AI_THRESHOLD
        }

    return translated, similarities
