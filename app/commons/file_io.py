# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import json
import os
from pathlib import Path
import contextlib
from tempfile import NamedTemporaryFile
from typing import Any, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

__all__ = ["read_json", "write_json"]


def read_json(file_path: str | Path, *, encoding: str = "utf-8") -> Any:
    """Read a JSON file.

    Args:
        file_path: Path to the JSON file.
        encoding: Text encoding to use when reading.

    Returns:
        Parsed JSON content.

    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")

    with path.open("r", encoding=encoding) as f:
        return json.load(f)


def write_json(
    file_path: str | Path,
    data: Any,
    *,
    encoding: str = "utf-8",
    indent: int | None = 2,
    ensure_ascii: bool = False,
    create_parents: bool = True,
    atomic: bool = True,
    default: Callable[[Any], Any] | None = None,
) -> None:
    """Write data to a JSON file.

    Writes using UTF-8 by default. When ``atomic`` is True, writes to a temporary
    file in the same directory and replaces the target to avoid partial writes.

    Args:
        file_path: Destination file path.
        data: JSON-serialisable object to write.
        encoding: Text encoding to use when writing.
        indent: Indentation level for pretty printing. ``None`` for compact.
        ensure_ascii: If True, escape non-ASCII characters.
        create_parents: Create parent directories if they do not exist.
        atomic: Use atomic replace to avoid torn writes.
        default: Optional JSON default serialiser callable for unsupported types.

    """
    path = Path(file_path)
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)


    if not atomic:
        with path.open("w", encoding=encoding, newline="\n") as f:
            json.dump(
                data,
                f,
                ensure_ascii=ensure_ascii,
                indent=indent,
                default=default or _json_default,
            )
            f.write("\n")
        return

    # Atomic write: write to a temporary file then replace
    with NamedTemporaryFile(
        mode="w",
        encoding=encoding,
        dir=str(path.parent),
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        tmp_path = Path(tmp.name)
        try:
            json.dump(
                data,
                tmp,
                ensure_ascii=ensure_ascii,
                indent=indent,
                default=default or _json_default,
            )
            tmp.write("\n")
            tmp.flush()
            os.fsync(tmp.fileno())
        except Exception:
            # Best-effort cleanup before re-raising
            try:
                tmp.close()
            finally:
                with contextlib.suppress(Exception):
                    tmp_path.unlink(missing_ok=True)
            raise

    os.replace(tmp_path, path)


def _json_default(value: Any) -> Any:
    """Fallback JSON serialiser for common non-serialisable types.

    Handles:
    - pathlib.Path ➜ str
    - set ➜ sorted list
    - CRS-like objects ➜ to_string() | to_wkt() | "EPSG:{code}"
    - numpy scalars (objects with .item()) ➜ native Python scalar
    - fallback ➜ str(value)
    """
    if isinstance(value, Path):
        return str(value)

    if isinstance(value, set):
        try:
            return sorted(value)
        except Exception:
            return list(value)

    to_string = getattr(value, "to_string", None)
    if callable(to_string):
        try:
            return to_string()
        except Exception:
            pass

    to_wkt = getattr(value, "to_wkt", None)
    if callable(to_wkt):
        try:
            return to_wkt()
        except Exception:
            pass

    to_epsg = getattr(value, "to_epsg", None)
    if callable(to_epsg):
        try:
            epsg = to_epsg()
            if epsg is not None:
                return f"EPSG:{epsg}"
        except Exception:
            pass

    item = getattr(value, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:
            pass

    return str(value)


