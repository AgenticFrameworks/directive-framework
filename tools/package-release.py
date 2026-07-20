#!/usr/bin/env python3
"""Build a reproducible, allowlisted directive-framework release archive."""
import gzip
import hashlib
import io
import json
import pathlib
import tarfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "dist"
# Single source of truth for the version: .claude-plugin/plugin.json.
# Bump it there and the release archive name follows.
VERSION = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
ALLOW = [
    "AUTO-HANDOFF-SPEC.md", "EXECUTOR-SPEC.md", "RUNTIME-SPEC.md", "README.md", "LICENSE",
    "gates", "tools", "planning-directives", "validation-directives", "review-directives",
    "execution-directives", ".claude-plugin", "portable", "tests",
]
EXCLUDED_PARTS = {"__pycache__", ".git", "dist", "_directives", "_archive"}


def files():
    result = []
    for item in ALLOW:
        path = ROOT / item
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(p for p in path.rglob("*") if p.is_file()
                          and not (set(p.relative_to(ROOT).parts) & EXCLUDED_PARTS))
    return sorted(result, key=lambda p: p.relative_to(ROOT).as_posix())


def main():
    OUT.mkdir(exist_ok=True)
    archive = OUT / f"directive-framework-v{VERSION}.tar.gz"
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in files():
            info = tar.gettarinfo(str(path), arcname=f"directive-framework/{path.relative_to(ROOT)}")
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = ""
            with open(path, "rb") as source:
                tar.addfile(info, source)
    with open(archive, "wb") as dest:
        with gzip.GzipFile(filename="", mode="wb", fileobj=dest, mtime=0) as gz:
            gz.write(raw.getvalue())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT / f"directive-framework-v{VERSION}.sha256").write_text(f"{digest}  {archive.name}\n")
    print(archive, digest)

if __name__ == "__main__":
    main()
