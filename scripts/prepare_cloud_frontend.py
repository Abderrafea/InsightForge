"""Build the web UI and copy only generated files into the cloud deployment root."""

import os
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    frontend = root / "frontend"
    destination = root / "backend" / "dist"
    if destination.is_symlink() or destination.resolve() != root / "backend" / "dist":
        raise SystemExit("Refusing to replace a build directory outside this workspace")
    npm = "npm.cmd" if os.name == "nt" else "npm"
    subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(frontend / "dist", destination)
    print("Built frontend copied to backend/dist for FastAPI Cloud")


if __name__ == "__main__":
    main()
