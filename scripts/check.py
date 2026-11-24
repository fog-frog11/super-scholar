from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def main() -> int:
    run([sys.executable, "-m", "compileall", "-q", "app", "tests"], ROOT / "backend")
    run([sys.executable, "-m", "pytest", "-q"], ROOT / "backend")
    if (ROOT / "frontend" / "node_modules").exists():
        run(["npm", "run", "typecheck"], ROOT / "frontend")
        run(["npm", "run", "build"], ROOT / "frontend")
    else:
        print("frontend/node_modules 不存在：跳过前端 typecheck/build。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
