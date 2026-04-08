from __future__ import annotations

import os

from api.main import app


def main() -> None:
    import uvicorn

    raw_port = os.getenv("PORT", "7860")
    try:
        port = int(raw_port)
    except ValueError:
        port = 7860

    uvicorn.run("server.app:app", host="0.0.0.0", port=port)


if __name__ == '__main__':
    main()
