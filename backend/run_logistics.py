"""Local entry point for the WMS/Logistics API (port 18005)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    backend_dir = Path(__file__).resolve().parent
    logistics_dir = backend_dir / "services" / "logistics"

    os.chdir(logistics_dir)
    sys.path.insert(0, str(logistics_dir))

    host = os.getenv("LOGISTICS_HOST", "0.0.0.0" if os.getenv("RENDER") else "127.0.0.1")
    port = int(os.getenv("PORT", os.getenv("LOGISTICS_PORT", "18005")))
    reload_enabled = False if os.getenv("RENDER") else os.getenv("LOGISTICS_RELOAD", "true").strip().lower() in {"1", "true", "yes"}

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=[str(logistics_dir)] if reload_enabled else None,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
