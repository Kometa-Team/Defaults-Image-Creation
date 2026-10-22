"""Reuse the pinned renderer's three inline wash statements, without editing it."""

import ast
from pathlib import Path

from PIL import Image

from ...common import BulkError, fingerprint

SOURCE = Path(__file__).resolve().parents[3] / "create_poster.py"
# Existing M3 transformation identity (Package E's canonical source-text hash).
SOURCE_SHA256 = "ff748c9c8422a46f662f36a094a3ef523d2f9c4c23d622729f18c1f1894e0717"


def implementation():
    text = SOURCE.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    if fingerprint(text) != SOURCE_SHA256:
        raise BulkError("logo_wash_source", "Approved renderer changed; no substitute wash is permitted")
    function = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == "render_poster")
    choices = [n for n in function.body if isinstance(n, ast.If) and ast.unparse(n.test) == "options.white_wash"]
    if len(choices) != 1 or len(choices[0].body) != 3 or choices[0].orelse:
        raise BulkError("logo_wash_shape", "Pinned inline wash is not available as the expected narrow operation")
    body = choices[0].body
    # Only the hash-pinned repository implementation is compiled; never submitted
    # Python/JSON, a whole renderer or a contributor-selected source path.
    module = ast.fix_missing_locations(ast.Module(body=body, type_ignores=[]))
    code = compile(module, str(SOURCE), "exec")
    return code, {"id": "existing-poster-white-wash", "version": "renderer-inline-m3-v1",
                  "source_sha256": SOURCE_SHA256, "body_sha256": fingerprint(ast.dump(module, include_attributes=False)),
                  "adapter_sha256": fingerprint(Path(__file__).read_text(encoding="utf-8").replace("\r\n", "\n")),
                  "parameters": {"preserve_original_alpha": True, "rgb": "white"}}


def white_wash(image):
    if image.mode != "RGBA":
        raise BulkError("logo_wash_mode", "Adapter requires validated RGBA input")
    code, provenance = implementation()
    scope = {"Image": Image, "logo": image.copy(), "__builtins__": {}}
    exec(code, scope)
    result = scope["logo"]
    if result.getchannel("A").tobytes() != image.getchannel("A").tobytes():
        raise BulkError("logo_wash_alpha", "Existing wash did not retain exact alpha")
    return result, provenance
