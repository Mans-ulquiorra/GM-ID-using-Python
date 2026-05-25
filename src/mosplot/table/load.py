from __future__ import annotations

import numpy as np


def load_lookup_table(path: str) -> dict:
    """Load a mosplot lookup table from an .npz file."""
    return np.load(path, allow_pickle=True)["lookup_table"].item()
