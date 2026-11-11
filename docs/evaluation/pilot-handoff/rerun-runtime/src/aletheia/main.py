"""Local-only command-line entry point."""

import sys

import uvicorn

from aletheia.api import create_app
from aletheia.config import ConfigurationError


def run() -> None:
    try:
        app = create_app()
    except ConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
    uvicorn.run(app, host="127.0.0.1", port=8000, workers=1, access_log=False)


if __name__ == "__main__":
    run()
