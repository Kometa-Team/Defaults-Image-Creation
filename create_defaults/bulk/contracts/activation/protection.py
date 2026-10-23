"""Read-only production nonintegration check at pinned production source bytes."""

import ast
import hashlib
from pathlib import Path

from ...common import BulkError, fingerprint
from ..models import decode_json, read_json_bytes


HERE = Path(__file__).parent
PRODUCTION_PINS_SHA256 = "4fdc201ab7d86138c003a38d30ce3bdb9e077819ad1037cb2698297c1d9089cf"


def verify(root=Path(__file__).parents[4]):
    pins = decode_json(read_json_bytes(HERE/"data/production-pins-v1.json"))
    if fingerprint(pins) != PRODUCTION_PINS_SHA256:
        raise BulkError("activation_production_pin", "The selected production pin set changed")
    checked = []
    for name, expected in pins["files"].items():
        raw = (root/name).read_bytes().replace(b"\r\n",b"\n")
        if hashlib.sha256(raw).hexdigest() != expected:
            raise BulkError("activation_production_changed", "Production source differs from the approved baseline: "+name)
        if name.endswith(".py"):
            try:
                tree = ast.parse(raw,filename=name)
            except SyntaxError:
                if name not in pins["historical_syntax_exceptions"]:
                    raise
                # An explicitly retained historical syntax exception still
                # requires its exact pinned bytes. The repaired sweeper no
                # longer has an exception in the selected manifest.
                checked.append(name)
                continue
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node,ast.ImportFrom):
                    names = [node.module or ""]+[a.name for a in node.names]
                elif isinstance(node,ast.Constant) and isinstance(node.value,str):
                    names = [node.value]
                else:
                    continue
                if any("contracts.activation" in n or "activation-controller" in n for n in names):
                    raise BulkError("activation_production_import", "Production entry point references the isolated controller")
        checked.append(name)
    return {"kind":"m7-production-nonactivation","baseline_commit":pins["baseline_commit"],
        "production_file_pins_sha256":fingerprint(pins),"production_files_verified":len(checked),
        "unchanged_historical_syntax_exceptions":pins["historical_syntax_exceptions"],
        "production_enforcement":False,"production_hooks":0,"production_flags":0,
        "actual_contracts_active":0,"publication_authorized":False}
