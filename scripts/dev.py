from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def spawn(command: list[str], cwd: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(command, cwd=cwd, env=os.environ.copy(), text=True)


def main() -> int:
    if not (FRONTEND / "node_modules").exists():
        print("frontend/node_modules 不存在，请先在 frontend 执行 npm install。", file=sys.stderr)
        return 2

    backend = spawn(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"],
        BACKEND,
    )
    frontend = spawn(["npm", "run", "dev"], FRONTEND)
    children = [backend, frontend]

    def stop(*_: object) -> None:
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    try:
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    stop()
                    return code
            time.sleep(0.25)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
