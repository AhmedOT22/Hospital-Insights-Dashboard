"""Validate generated PBIR files against Microsoft's published JSON schemas."""

import json
from pathlib import Path
from urllib.request import urlopen
from referencing import Registry, Resource
from jsonschema import Draft7Validator
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("/tmp/hospital-pbir-schemas")
CACHE.mkdir(exist_ok=True)


def retrieve(uri):
    if urlparse(uri).netloc != "developer.microsoft.com":
        raise ValueError("Unexpected schema host")
    import hashlib

    p = CACHE / (hashlib.sha256(uri.encode()).hexdigest() + ".json")
    if not p.exists():
        with urlopen(uri, timeout=30) as r:
            p.write_bytes(r.read())
    return Resource.from_contents(json.loads(p.read_text()))


registry = Registry(retrieve=retrieve)
paths = list((ROOT / "PowerBI/Hospital.Report").rglob("*.json")) + [
    ROOT / "PowerBI/Hospital.Report/definition.pbir"
]
for path in paths:
    d = json.loads(path.read_text())
    uri = d.get("$schema")
    if not uri:
        continue
    schema = retrieve(uri).contents
    errors = list(Draft7Validator(schema, registry=registry).iter_errors(d))
    if errors:
        for e in errors[:10]:
            print(path.relative_to(ROOT), list(e.path), e.message)
        raise SystemExit(1)
print("PBIR files match published Microsoft JSON schemas.")
