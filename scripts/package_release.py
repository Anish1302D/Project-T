"""Build reproducible release artifacts (Python wheels, MV3 bundle, VS Code bundle, Dashboard bundle)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "dist" / "release"

PYTHON_PACKAGES = [
    ROOT / "packages" / "contracts",
    ROOT / "packages" / "optimization-core",
    ROOT / "packages" / "provider-adapters",
    ROOT / "apps" / "local-runtime",
    ROOT / "apps" / "api-gateway",
    ROOT / "services",
]


def _zip_directory(source_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.relative_to(source_dir))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if RELEASE_DIR.exists():
        shutil.rmtree(RELEASE_DIR)
    wheels_dir = RELEASE_DIR / "wheels"
    wheels_dir.mkdir(parents=True, exist_ok=True)

    # 1. Build Python wheels (no-deps; honors offline build isolation cache if present)
    for pkg in PYTHON_PACKAGES:
        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheels_dir), str(pkg)],
            cwd=ROOT,
            check=True,
        )

    # 2. Chrome MV3 bundle
    ext_dist = ROOT / "apps" / "browser-extension" / "dist"
    if not (ext_dist / "manifest.json").exists():
        raise FileNotFoundError(f"Missing built browser extension at {ext_dist}")
    _zip_directory(ext_dist, RELEASE_DIR / "project-t-browser-extension-mv3-v1.0.0.zip")

    # 3. Cloud Dashboard static web bundle
    dash_dist = ROOT / "apps" / "dashboard" / "dist"
    if not (dash_dist / "index.html").exists():
        raise FileNotFoundError(f"Missing built dashboard at {dash_dist}")
    _zip_directory(dash_dist, RELEASE_DIR / "project-t-dashboard-web-v1.0.0.zip")

    # 4. VS Code extension bundle (archive package.json + compiled dist/extension.js, or .vsix via vsce)
    vsc_dir = ROOT / "apps" / "vscode-extension"
    if not (vsc_dir / "dist" / "extension.js").exists():
        raise FileNotFoundError(f"Missing built VS Code extension at {vsc_dir / 'dist'}")
    vsc_zip = RELEASE_DIR / "project-t-vscode-extension-v1.0.0.zip"
    with zipfile.ZipFile(vsc_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(vsc_dir / "package.json", arcname="package.json")
        if (vsc_dir / "README.md").exists():
            zf.write(vsc_dir / "README.md", arcname="README.md")
        for file_path in sorted((vsc_dir / "dist").rglob("*")):
            if file_path.is_file():
                zf.write(file_path, arcname=file_path.relative_to(vsc_dir))

    # 5. Emit SHA256SUMS manifest
    checksum_lines: list[str] = []
    for artifact in sorted(RELEASE_DIR.rglob("*")):
        if artifact.is_file() and artifact.name != "SHA256SUMS.txt":
            rel = artifact.relative_to(RELEASE_DIR).as_posix()
            checksum_lines.append(f"{_sha256_file(artifact)}  {rel}")
    (RELEASE_DIR / "SHA256SUMS.txt").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    print(f"Packaged {len(checksum_lines)} release artifacts into {RELEASE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
