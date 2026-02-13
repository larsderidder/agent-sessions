"""Path normalization utilities."""

from __future__ import annotations

from pathlib import Path


def normalize_directory_path(path: str) -> str:
    """Return a normalized absolute path for the provided directory string."""
    candidate = Path(path).expanduser()
    try:
        resolved = candidate.resolve(strict=False)
    except FileNotFoundError:
        resolved = candidate
    return str(resolved)
