"""Optional numba compatibility helpers used across mosplot."""

from __future__ import annotations

try:
    from numba import njit  # type: ignore[import]
except ImportError:

    def njit(**_kw):  # type: ignore[misc]
        """Return an identity decorator when numba is unavailable."""

        def _wrap(fn):
            return fn

        return _wrap
