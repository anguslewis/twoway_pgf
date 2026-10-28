"""Build the wheel, Stata payload, metadata and checksums.

Run with the pinned environment from the package root. Outputs are confined to
artifacts/, bootstrap/pins.sh, stata/_twoway_pgf_package.ado and the net metadata.
"""
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EPOCH = "1791417600"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wheel(version):
    with tempfile.TemporaryDirectory(prefix="twoway-pgf-build-") as directory:
        source = Path(directory) / "source"
        shutil.copytree(ROOT, source, ignore=shutil.ignore_patterns(
            "artifacts", "__pycache__", "*.egg-info", "build", "dist", ".git"))
        subprocess.run([
            sys.executable, "-m", "pip", "wheel", "--no-cache-dir", "--no-index", "--no-deps",
            "--no-build-isolation", "--wheel-dir", directory, str(source),
        ], env={**os.environ, "SOURCE_DATE_EPOCH": EPOCH}, check=True)
        built = Path(directory) / f"twoway_pgf-{version}-py3-none-any.whl"
        target = ROOT / "artifacts" / built.name
        shutil.copy2(built, target)
        return target


def stata_payload(version, built):
    target = ROOT / "artifacts" / f"twoway_pgf_stata-{version}.zip"
    files = [ROOT / "LICENSE", ROOT / "NOTICES", ROOT / "environment.yml", built]
    files += sorted((ROOT / "bootstrap").glob("*"))
    files += sorted((ROOT / "stata").glob("*.py"))
    files += sorted((ROOT / "locks").glob("*.txt"))
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(p for p in files if p.is_file()):
            info = zipfile.ZipInfo(path.relative_to(ROOT).as_posix(), (2026, 10, 8, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, path.read_bytes())
    helper = ROOT / "stata/_twoway_pgf_package.ado"
    text, count = re.subn(r'local payload_id "[^"]+"',
                         f'local payload_id "{version}-{sha256(target)[:12]}"', helper.read_text())
    if count != 1:
        raise ValueError("Expected exactly one payload identifier in the Stata helper")
    helper.write_text(text)
    # Uppercase F entries install Python and ZIP assets onto the adopath.
    # The helper unpacks the payload into the package's cache.
    entries = ["v 3", f"d twoway_pgf {version}: LaTeX-native figures from Stata and Python",
               "d Angus Lewis", "d Requires Stata 16+, external Python and TeX"]
    for path in sorted((ROOT / "stata").iterdir()):
        if path.suffix in {".ado", ".sthlp", ".py"}:
            flag = "F" if path.suffix == ".py" else "f"
            entries.append(f"{flag} {path.relative_to(ROOT).as_posix()}")
    entries += [f"F artifacts/{target.name}", "e"]
    (ROOT / "twoway_pgf.pkg").write_text("\n".join(entries) + "\n")
    (ROOT / "stata.toc").write_text("v 3\nd twoway_pgf\np twoway_pgf LaTeX-native figures from Stata and Python\n")
    return target


def main():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    for name in ["src/twoway_pgf/__init__.py", "stata/twoway_pgf_setup.ado",
                 "stata/twoway_pgf_bridge.py", "bootstrap/register.py"]:
        if version not in (ROOT / name).read_text():
            raise ValueError(f"Version {version} missing from {name}")
    (ROOT / "artifacts").mkdir(exist_ok=True)
    built = wheel(version)
    (ROOT / "bootstrap/pins.sh").write_text(f'''# Pinned build metadata.
VERSION={version}
WHEEL_NAME={built.name}
WHEEL_SHA256={sha256(built)}
LOCK_OSX_SHA256={sha256(ROOT / 'locks/osx-arm64.txt')}
LOCK_LINUX_SHA256={sha256(ROOT / 'locks/linux-64.txt')}
''')
    payload = stata_payload(version, built)
    print(f"{built.name}: {sha256(built)}")
    print(f"{payload.name}: {sha256(payload)}")


if __name__ == "__main__":
    main()
