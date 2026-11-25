"""Local entry point for the Aethereon Finance API (port 18002)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    backend_dir = Path(__file__).resolve().parent
    finance_dir = backend_dir / "services" / "finance"

    os.chdir(finance_dir)
    sys.path.insert(0, str(finance_dir))

    host = os.getenv("FINANCE_HOST", "0.0.0.0" if os.getenv("RENDER") else "127.0.0.1")
    port = int(os.getenv("PORT", os.getenv("FINANCE_PORT", "18002")))
    reload_enabled = False if os.getenv("RENDER") else os.getenv("FINANCE_RELOAD", "true").strip().lower() in {"1", "true", "yes"}

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=[str(finance_dir)] if reload_enabled else None,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
