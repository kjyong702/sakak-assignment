from __future__ import annotations

import uvicorn

from app.core.settings import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run("app.main:app", port=settings.port)


if __name__ == "__main__":
    main()
