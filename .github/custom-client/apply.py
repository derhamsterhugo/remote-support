"""Apply a custom-client bundle to the source tree.

The bundle is a base64 zip passed via the CLIENT_BUNDLE secret. It contains a
manifest.json (text replacements, asset copies, values to mask), the asset
files and a signed custom.txt. Nothing client-specific lives in the repo.
"""

import base64
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def emit(line):
    print(line, flush=True)


def set_output(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def replace_in_lang_values(path, name):
    # Only touch the translated value, never the lookup key.
    pat = re.compile(r'^(\s*\(".*?",\s*")(.*)("\),?\s*)$')
    lines = read(path).splitlines(keepends=True)
    changed = False
    for i, line in enumerate(lines):
        m = pat.match(line.rstrip("\r\n"))
        if m and "RustDesk" in m.group(2):
            eol = line[len(line.rstrip("\r\n")):]
            lines[i] = m.group(1) + m.group(2).replace("RustDesk", name) + m.group(3) + eol
            changed = True
    if changed:
        write(path, "".join(lines))


def main():
    raw = os.environ.get("CLIENT_BUNDLE", "").strip()
    if not raw:
        sys.exit("CLIENT_BUNDLE secret is missing")
    work = ROOT / ".custom-bundle"
    work.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(raw))) as z:
        z.extractall(work)
    manifest = json.loads((work / "manifest.json").read_text(encoding="utf-8"))

    for value in manifest.get("mask", []):
        emit(f"::add-mask::{value}")

    for rep in manifest["replace"]:
        path = ROOT / rep["file"]
        text = read(path)
        if rep["from"] not in text:
            sys.exit(f"replacement #{manifest['replace'].index(rep)} not found in {rep['file']}")
        write(path, text.replace(rep["from"], rep["to"]))

    for src, targets in manifest["copy"].items():
        if src.endswith("@"):
            # derived file: build the .ico from icon.png
            from PIL import Image

            img = Image.open(work / "icon.png").convert("RGBA")
            data = io.BytesIO()
            img.save(data, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
            blob = data.getvalue()
        else:
            blob = (work / src).read_bytes()
        for t in targets:
            (ROOT / t).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / t).write_bytes(blob)

    name = manifest.get("lang_app_name")
    if name:
        for p in (ROOT / "src" / "lang").glob("*.rs"):
            if p.name != "template.rs":
                replace_in_lang_values(p, name)

    (ROOT / ".custom-bundle" / "artifact_pub.pem").write_text(manifest["artifact_pubkey_pem"], encoding="ascii")
    set_output("exe_name", manifest["exe_name"])
    emit(f"applied {len(manifest['replace'])} replacements, {len(manifest['copy'])} assets")


if __name__ == "__main__":
    main()
