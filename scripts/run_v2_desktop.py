"""Launch V2 on an owned loopback socket; never reuse or stop another service."""
from __future__ import annotations

import argparse
import os
import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="启动入排审核工作台")
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--frontend-dir", type=Path, default=Path(__file__).resolve().parents[1] / "frontend/dist")
    parser.add_argument("--browse-only", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()

    # Load only the product env contract, before constructing any application.
    os.environ["ENROLLMENT_ENV_FILE"] = str(args.env_file.expanduser().resolve())
    from app import config as _config
    from app.api.v2.desktop import create_desktop_app
    from app.services.evidence_app_bootstrap import resolve_data_paths

    data_dir = str(args.data_dir) if args.data_dir else os.environ.get("ENROLLMENT_V2_DATA_DIR", "")
    if args.port < 0 or args.port > 65535:
        raise RuntimeError("工作台端口不正确，请检查启动配置。")
    app = create_desktop_app(
        frontend_dir=args.frontend_dir,
        data_paths=resolve_data_paths(data_dir or None), browse_only=args.browse_only,
    )
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", args.port))
        port = listener.getsockname()[1]
        url = f"http://127.0.0.1:{port}/" + ("#/reports" if args.browse_only else "#/protocols")
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port))
        finished = threading.Event()

        def open_when_ready():
            while not finished.wait(0.1):
                if server.started:
                    print(f"入排审核工作台已打开：{url}", flush=True)
                    if not args.no_browser:
                        webbrowser.open(url)
                    return

        browser = threading.Thread(target=open_when_ready, daemon=True)
        browser.start()
        try:
            try:
                server.run(sockets=[listener])
            except KeyboardInterrupt:
                pass
        finally:
            finished.set()
            browser.join(timeout=1)
        if not server.started:
            raise RuntimeError("工作台未能启动。资料未被当作已审核；可选择仅查看方式查阅已有报告。")


if __name__ == "__main__":
    main()
