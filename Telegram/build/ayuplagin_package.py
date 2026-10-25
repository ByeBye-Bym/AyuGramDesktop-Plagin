# Packs a Release build into Ayuplagin-<version>-win64.zip.
# Usage: python ayuplagin_package.py <build dir with Ayuplagin.exe> <version> <output dir>

import hashlib
import os
import sys
import zipfile

# Public test keys from the build docs, Telegram rejects apps shipped with them.
TEST_HASHES = [b"b18441a1ff607e10a989891a5462e627", b"344583e45741c457fe1862106095a5eb"]

build, version, out_dir = sys.argv[1:4]
exe = os.path.join(build, "Ayuplagin.exe")
with open(exe, "rb") as f:
    binary = f.read()
if any(h in binary for h in TEST_HASHES):
    sys.exit("Ayuplagin.exe is built with public test api_hash, rebuild with your own keys.")
if not os.path.isfile(os.path.join(build, "python", "python311.dll")):
    sys.exit("python/ runtime is missing next to the exe.")
if not os.path.isfile(os.path.join(build, "python", "sdk", "api.tl")):
    sys.exit("python/sdk/api.tl is missing, request hooks would not work.")

root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.makedirs(out_dir, exist_ok=True)
target = os.path.join(out_dir, f"Ayuplagin-{version}-win64.zip")
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    z.write(exe, "Ayuplagin/Ayuplagin.exe")
    for name in ("LICENSE", "LEGAL"):
        z.write(os.path.join(root, name), "Ayuplagin/" + name)
    for folder, dirs, files in os.walk(os.path.join(build, "python")):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "test", "tests")]
        for name in files:
            if name.endswith((".pyc", ".pdb")):
                continue
            path = os.path.join(folder, name)
            z.write(path, "Ayuplagin/" + os.path.relpath(path, build).replace("\\", "/"))

with open(target, "rb") as f:
    digest = hashlib.sha256(f.read()).hexdigest()
print(target)
print(f"SHA256 {digest}")
