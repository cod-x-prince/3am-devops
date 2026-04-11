from __future__ import annotations

import logging
import os

from api.main import app


def main() -> None:
    import uvicorn

    raw_port = os.getenv("PORT", "7860")
    log_level = os.getenv("LOG_LEVEL", "info").lower()
    try:
        port = int(raw_port)
    except ValueError:
        port = 7860

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run(app, host="0.0.0.0", port=port, log_level=log_level)


if __name__ == '__main__':
    main()
