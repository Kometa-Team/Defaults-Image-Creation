"""Canonical, non-rendering plans from explicit definitions and input identities."""

from dataclasses import asdict
from importlib.metadata import version
import json
import inspect
from functools import lru_cache
from itertools import islice
from pathlib import Path
import platform

from create_defaults.create_poster import PosterOptions, integer, output_filename
from create_defaults.poster_text import load_layout
from .common import BulkError, canonical, confined, fingerprint, normalize_hex, path_key, sha256
from .config import Config, LANGUAGES, select_categories, select_languages
from .definitions import Definition, FORMATS, StrictValidator, validate_schema


SHARED_ASSETS = ("transparent.png", "fades/@none.png", "fades/@center-out-fade.png", "fades/@bottom-up-fade.png", "fades/@top-down-fade.png", "fades/@bottom-top-fade.png")


@lru_cache(maxsize=1)
def _composer_validator():
    definition = json.loads((Path(__file__).resolve().parent / "schemas/definition-v1.json").read_text(encoding="utf-8"))
    return StrictValidator({"$defs": definition["$defs"], "$ref": "#/$defs/composer"}, format_checker=FORMATS)


def renderer_identity():
    root = Path(__file__).resolve().parents[1]
    sources = {name: fingerprint((root / name).read_text(encoding="utf-8-sig").replace("\r\n", "\n")) for name in ("create_poster.py", "poster_text.py")}
    return {"sources": sources, "python": platform.python_version(), "platform": platform.system(),
            "libraries": {name: version(name) for name in ("Pillow", "fonttools", "uharfbuzz", "python-bidi")},
            "encoding": {"format": "JPEG", "quality": 100, "subsampling": 0}, "canvas": [2000, 3000]}


def effective_parameters(raw):
    if set(raw) != set(PosterOptions.__dataclass_fields__):
        raise BulkError("incomplete_parameters", "All composer parameters must be explicit")
    result = dict(raw)
    for name in ("logo_offset", "text_offset"):
        result[name] = integer(raw[name], name, -1500, 1500)
    result["logo_resize"] = integer(raw["logo_resize"] or 2000, "logo_resize", 1, 2000)
    for name, low, high, fallback in (("font_size", 10, 500, 250), ("border_width", 1, 100, 15)):
        value = integer(raw[name] or fallback, name, -1_000_000, 1_000_000)
        result[name] = value if low <= value <= high else fallback
    value = integer(raw["gradient"], "gradient", -1_000_000, 1_000_000)
    result["gradient"] = value if 0 <= value <= 4 else 1
    for name in ("base_color", "font_color", "border_color"):
        result[name] = normalize_hex(raw[name])
    return result


def validate_manifest(value):
    validate_schema(value, "manifest-v1.json")
    payload = {key: item for key, item in value.items() if key != "sha256"}
    if fingerprint(payload) != value["sha256"]:
        raise BulkError("corrupt_manifest", "Manifest fingerprint mismatch")
    identities, local_paths, remote_paths = set(), set(), set()
    seen = set()
    for job in value["jobs"]:
        if job["id"] in identities:
            raise BulkError("duplicate_job", "Duplicate job identity")
        identities.add(job["id"])
        for dependency in job["dependencies"]:
            if dependency["job_id"] not in seen:
                raise BulkError("invalid_dependency", "Dependencies must be present and topologically ordered")
        seen.add(job["id"])
        for field, paths in (("local_relative", local_paths), ("remote_relative", remote_paths)):
            path = job[field]
            if path is not None:
                key = path_key(path)
                if key in paths:
                    raise BulkError("output_collision", "Conflicting active output paths")
                paths.add(key)
        if job["kind"] == "poster":
            if not _composer_validator().is_valid(job["raw_parameters"]):
                raise BulkError("incomplete_parameters", "Raw composer types/fields are invalid")
            if set(job["raw_parameters"]) != set(PosterOptions.__dataclass_fields__) or job["parameters"] != effective_parameters(job["raw_parameters"]):
                raise BulkError("incomplete_parameters", "Invalid raw/effective composer record")
        elif job["render_ready"] and (job["parameters"] != job["raw_parameters"] or value["renderer"]["encoding"] != {"format": "PNG", "compress_level": 9}
                or job["parameters"]["resampling"] != "Pillow-LANCZOS" or "bulk/overlays.py" not in value["renderer"]["sources"]
                or job["parameters"]["box"] not in ([285, 85], [440, 100])
                or not job["local_relative"].endswith(".png")
                or not any(i["role"] == "overlay_source" and i["path"] == job["parameters"]["input"] for i in job["inputs"])):
            raise BulkError("invalid_overlay", "Overlay parameters/encoding differ from executable contract")
        expected = fingerprint({key: job[key] for key in ("kind", "parameters", "inputs", "dependencies", "language_behavior")} | {"renderer": value["renderer"]})
        if expected != job["render_fingerprint"]:
            raise BulkError("corrupt_manifest", "Render fingerprint mismatch")
    return value


class Planner:
    def __init__(self, config=None, *, generators=None, scope=None):
        self.config = config or Config()
        self.generators = generators or {}
        self.scope = scope or "representative infrastructure plan; no render/approval or full-category coverage"

    def expand(self, definitions):
        """Expose the validated graph without claiming generated bytes exist."""
        expanded, families, origins = [], {}, {}
        if len({item.id for item in definitions}) != len(definitions):
            raise BulkError("invalid_selection", "Duplicate or unknown logical poster identity")
        for definition in definitions:
            generator = definition.data["generator"]
            if generator is None:
                expanded.append(definition)
                continue
            callback = self.generators.get((generator["name"], generator["version"]))
            if callback is None:
                raise BulkError("unknown_generator", "Named Python generator is not registered; no expressions are evaluated")
            children = list(islice(callback(definition, generator["parameters"]), 100001))
            if not children or len(children) > 100000:
                raise BulkError("invalid_generator", "Generator expansion is empty or exceeds its safety limit")
            try:
                code_sha = fingerprint(inspect.getsource(callback))
            except (OSError, TypeError) as error:
                raise BulkError("invalid_generator", "Registered generators require inspectable versioned Python source") from error
            families[definition.id] = []
            for child in children:
                if not isinstance(child, Definition) or child.data["generator"] is not None:
                    raise BulkError("invalid_generator", "Generators must return complete non-recursive Definition records")
                child = Definition.create(child.data)
                expanded.append(child)
                families[definition.id].append(child.id)
                origins[child.id] = {"specification": {"name": generator["name"], "version": generator["version"], "parameters_sha256": fingerprint(generator["parameters"])},
                                     "parent_fingerprint": definition.fingerprint, "code_sha256": code_sha}
        catalog = {item.id: item for item in expanded}
        if len(catalog) != len(expanded):
            raise BulkError("duplicate_definition", "Generated logical identities conflict")
        return catalog, families, origins

    def plan(self, definitions, translations, *, categories=(), posters=(), languages=("en",), dependency_artifacts=None):
        declared = {language for definition in definitions for language in definition.data["languages"]}
        categories, languages = select_categories(categories), select_languages(languages, available=set(LANGUAGES) | set(translations.sources) | declared)
        if not languages or (not categories and not posters):
            raise BulkError("empty_selection", "Select categories/poster IDs and languages explicitly")
        catalog, families, origins = self.expand(definitions)
        selected_posters = set()
        for identity in posters:
            if identity in families:
                selected_posters.update(families[identity])
            elif identity in catalog:
                selected_posters.add(identity)
            else:
                raise BulkError("invalid_selection", "Unknown logical poster identity")
        selected = {key for key, item in catalog.items() if (not categories or item.category in categories) and (not posters or key in selected_posters)}
        if not selected:
            raise BulkError("empty_selection", "No representative definitions match this selection")
        ordered, visiting, visited = [], set(), set()
        def visit(identity):
            if identity in visiting:
                raise BulkError("dependency_cycle", "Cyclic generated-input dependency")
            if identity in visited:
                return
            if identity not in catalog:
                raise BulkError("missing_dependency", "Missing logical dependency definition")
            visiting.add(identity)
            for dependency in sorted(catalog[identity].data["dependencies"], key=lambda item: item["poster_id"]):
                visit(dependency["poster_id"])
            visiting.remove(identity)
            visited.add(identity)
            ordered.append(identity)
        for identity in sorted(selected):
            visit(identity)
        renderer, jobs, by_identity, skipped = renderer_identity(), [], {}, []
        input_hashes = {}
        def input_hash(path):
            if path not in input_hashes:
                input_hashes[path] = sha256(confined(self.config.asset_dir, path, must_exist=True))
            return input_hashes[path]
        provenance = json.loads((Path(__file__).resolve().parent / "baselines/approved-fonts.json").read_text(encoding="utf-8"))["fonts"]
        for identity in ordered:
            definition = catalog[identity]
            for language in languages:
                item = definition.for_language(language).data
                applicability = item["applicability"].get(language)
                if applicability and applicability["status"] == "not_applicable":
                    skipped.append({"poster_id": identity, "language": language, "reason": applicability["reason"]})
                    continue
                if language not in item["languages"] or not applicability or applicability["status"] != "applicable":
                    raise BulkError("unknown_applicability", "Language applicability must be explicit, not inferred from missing translations")
                caption = translations.resolve(item["caption"], language)
                raw = dict(item["composer"], text=caption.text)
                font = confined(self.config.asset_dir, raw["font"], must_exist=True)
                font_sha = input_hash(raw["font"])
                if provenance.get(raw["font"]) != font_sha:
                    raise BulkError("unapproved_font", "Font lacks hash-bound approved bundled provenance")
                if caption.text:
                    try:
                        load_layout(str(font), font.stat().st_mtime_ns).validate(caption.text)
                    except ValueError as error:
                        raise BulkError("missing_glyph", str(error)) from error
                measurement = item["layout"]["measurement"]
                if item["layout"]["kind"] == "captured_fit" and (measurement["text"] != caption.text or measurement["font_sha256"] != font_sha or measurement["point_size"] != raw["font_size"]):
                    raise BulkError("stale_measurement", "Captured fitting does not bind this exact caption/font/size; obtain new layout evidence")
                parameters = effective_parameters(raw)
                filename = output_filename(PosterOptions(**parameters), parameters["base_color"])
                if filename != item["output"]["filename"]:
                    raise BulkError("output_mismatch", "Explicit output filename differs from composer behavior")
                local = "/".join(filter(None, (f"defaults-{language}", item["output"]["directory"], filename)))
                if language not in item["output"]["remote_paths"]:
                    raise BulkError("unknown_remote_path", "Remote mapping must be explicit; null means unconfirmed")
                dependencies, generated_inputs = [], set()
                for dependency in item["dependencies"]:
                    parent = by_identity.get((dependency["poster_id"], language))
                    if parent is None:
                        raise BulkError("missing_dependency", "Required parent language is not applicable/present")
                    artifact = (dependency_artifacts or {}).get(parent["id"])
                    if artifact is None:
                        raise BulkError("unresolved_dependency", "Provide a verified parent artifact identity before planning a dependent render")
                    if raw[dependency["input"]] != parent["local_relative"]:
                        raise BulkError("dependency_mapping_mismatch", "Generated input must explicitly identify its parent output path")
                    path = confined(self.config.output_dir, parent["local_relative"], must_exist=True)
                    if sha256(path) != artifact:
                        raise BulkError("corrupt_artifact", "Generated dependency artifact hash mismatch")
                    dependencies.append({"job_id": parent["id"], "input": dependency["input"], "sha256": artifact, "render_fingerprint": parent["render_fingerprint"]})
                    generated_inputs.add(dependency["input"])
                inputs = [{"role": "font", "path": raw["font"], "sha256": font_sha}]
                for path in SHARED_ASSETS:
                    inputs.append({"role": "shared", "path": path, "sha256": input_hash(path)})
                for name in ("logo", "avg_color_image", "dom_color_image"):
                    active = name == "logo" or (name == "avg_color_image" and raw["avg_color"] and not raw["base_color"])
                    if raw[name] and name not in generated_inputs and active:
                        inputs.append({"role": name, "path": raw[name], "sha256": input_hash(raw[name])})
                job = {"id": "poster." + fingerprint({"poster_id": identity, "language": language, "variant": "base"})[:24],
                    "kind": "poster", "poster_id": identity, "language": language, "variant": "base",
                    "definition_fingerprint": fingerprint({"definition": item, "generator_origin": origins.get(identity)}),
                    "generator_origin": origins.get(identity), "source": item["source"], "raw_parameters": raw, "parameters": parameters,
                    "inputs": sorted(inputs, key=lambda value: (value["role"], value["path"])), "dependencies": dependencies,
                    "translation": {"mode": caption.mode, "trace": list(caption.trace), "fingerprint": caption.fingerprint},
                    "language_behavior": {"language": language if caption.mode == "translation" else "shared", "direction": item["caption"]["direction"]},
                    "local_relative": local, "remote_relative": item["output"]["remote_paths"][language],
                    "layout_evidence": item["layout"], "color_assignment": item["color_assignment"], "status": "planned",
                    "render_ready": item["caption"]["direction"] == "auto"}
                job["render_fingerprint"] = fingerprint({key: job[key] for key in ("kind", "parameters", "inputs", "dependencies", "language_behavior")} | {"renderer": renderer})
                jobs.append(job)
                by_identity[(identity, language)] = job
        result = {"schema_version": 1, "kind": "bulk-plan", "renderer": renderer, "jobs": jobs,
                  "selection": {"categories": list(categories), "posters": sorted(posters), "languages": list(languages)},
                  "not_applicable": skipped, "scope": self.scope}
        result["sha256"] = fingerprint(result)
        return validate_manifest(result)
