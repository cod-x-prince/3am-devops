from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

# Make the nested project importable when running from repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
NESTED_PROJECT = PROJECT_ROOT / "incident-env"
if str(NESTED_PROJECT) not in sys.path:
    sys.path.insert(0, str(NESTED_PROJECT))

from api.main import app  # noqa: E402


def main() -> None:
    raw_port = os.getenv("PORT", "7860")
    try:
        port = int(raw_port)
    except ValueError:
        port = 7860

    uvicorn.run("server.app:app", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
