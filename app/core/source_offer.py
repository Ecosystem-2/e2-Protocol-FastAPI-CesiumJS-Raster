# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Where remote users get the source, as AGPL section 13 obliges us to tell them."""

import os
from pathlib import Path

_LICENCE_FILE = Path(__file__).resolve().parent.parent.parent / "LICENSE.md"

LICENCE = "AGPL-3.0-or-later"
COPYRIGHT = "Copyright (c) 2025-2026 Ecosystem2 Ltd and Yang Zhang"
WARRANTY = "This program comes with ABSOLUTELY NO WARRANTY."


def source_url() -> str | None:
    """The Corresponding Source for the version running in this process.

    Deliberately has no default. Whoever deploys this owes their users the source of
    what they deployed, and a baked-in guess would answer that question wrongly and
    silently. Unset means we say so rather than point somewhere plausible.
    """
    url = os.getenv("SOURCE_URL")
    return url.rstrip("/") if url else None


def revision() -> str | None:
    """The commit this build came from, baked in by the Dockerfile at build time.

    Without it the offer points at a moving branch, which tells a user what the code
    looks like now rather than what is answering their requests.
    """
    return os.getenv("SOURCE_REVISION") or None


def licence_text() -> str | None:
    """The licence as shipped, so the notice resolves without leaving the deployment."""
    try:
        return _LICENCE_FILE.read_text(encoding="utf-8")
    except OSError:
        return None


def offer() -> dict[str, str | None]:
    """The section 13 offer, in the shape the demo footer and API callers both read."""
    rev = revision()
    return {
        "licence": LICENCE,
        "copyright": COPYRIGHT,
        "warranty": WARRANTY,
        "source": source_url(),
        "revision": rev,
        "licence_text": "/licence",
    }
