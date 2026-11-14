"""Local entry point for the Aethereon Identity API (port 18001)."""
from __future__ import annotations

import os
import json
import sys
from pathlib import Path

import uvicorn


def main() -> None:
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    identity_dir = backend_dir / "services" / "identity"

    # Pydantic settings loads project-private environment relative to this root.
    os.chdir(project_root)
    sys.path.insert(0, str(identity_dir))

    host = os.getenv("IDENTITY_HOST", "127.0.0.1")
    port = int(os.getenv("IDENTITY_PORT", "18001"))
    reload_enabled = os.getenv("IDENTITY_RELOAD", "true").strip().lower() in {"1", "true", "yes"}

    # Windows may reserve a development port for another process/AppContainer.
    # Pick the first allowed port without binding a probe socket (uvicorn owns
    # the one and only bind; no race or leaked socket between probe and launch).
    if os.getenv("IDENTITY_AUTO_PORT", "false").strip().lower() in {"1", "true", "yes"}:
        import socket

        start = max(port, 18001)
        for candidate in range(start, min(start + 20, 18100)):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                try:
                    probe.bind((host, candidate))
                    port = candidate
                    break
                except OSError:
                    continue
        else:
            raise RuntimeError("No hay un puerto libre para identidad en el rango local acordado 18001–18100.")
        os.environ["IDENTITY_PORT"] = str(port)
        print(f"Aethereon Identity escuchará en {host}:{port}", flush=True)

    if os.getenv("IDENTITY_UPDATE_FRONTEND_PROXY", "true").strip().lower() in {"1", "true", "yes"}:
        proxy_file = project_root / "frontend" / "proxy.conf.json"
        if proxy_file.is_file():
            proxy_config = json.loads(proxy_file.read_text(encoding="utf-8"))
            if "/api" in proxy_config:
                proxy_config["/api"]["target"] = f"http://{host}:{port}"
                proxy_file.write_text(json.dumps(proxy_config, indent=2) + "\n", encoding="utf-8")
                print(f"Proxy /api configurado a http://{host}:{port}", flush=True)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        reload_dirs=[str(identity_dir)] if reload_enabled else None,
        log_level=os.getenv("LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
