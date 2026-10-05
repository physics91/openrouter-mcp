"""Helpers for replacing files atomically."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from typing import TextIO


def replace_file_atomically(
    destination: str,
    directory: str,
    writer: Callable[[TextIO], None],
    *,
    encoding: str | None = None,
    newline: str | None = None,
) -> None:
    """Write a temporary file and replace *destination*, cleaning up on failure."""
    fd, tmp_path = tempfile.mkstemp(dir=directory or ".", suffix=".tmp")
    try:
        if encoding is None:
            opened_file = os.fdopen(fd, "w")
        else:
            opened_file = os.fdopen(fd, "w", encoding=encoding, newline=newline)
        with opened_file as handle:
            writer(handle)
        os.replace(tmp_path, destination)
    except BaseException:
        os.unlink(tmp_path)
        raise
