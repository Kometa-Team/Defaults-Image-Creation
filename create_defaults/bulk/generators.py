"""Named, deterministic category expansions; no source evaluation or rendering."""

from pathlib import PurePosixPath
import re

from .common import BulkError, fingerprint, normalize_hex, relative_path
from .definitions import Definition


def poster_id(category, output):
    slug = re.sub(r"[^a-z0-9]+", "-", output.removesuffix(".jpg").lower()).strip("-")
    return category.lower() + "." + slug[:100] + "." + fingerprint(output)[:8]


def _child(base, filename, directory):
    relative_path(filename)
    if directory:
        relative_path(directory)
    output = "/".join(filter(None, (directory, filename)))
    value = base.data
    value["generator"] = None
    value["id"] = poster_id(value["category"], output)
    value["composer"]["out_name"] = PurePosixPath(filename).stem
    value["display_name"] = PurePosixPath(filename).stem
    value["output"] = {"directory": directory, "filename": filename, "remote_paths": {"en": output}}
    # Generated siblings are explicitly linked logical variants, not unrelated
    # independent color assignments repeated once for every rendered year.
    value["color_assignment"] = dict(value["color_assignment"], parent=base.id)
    return value


def _measurement(value, item, text):
    if not isinstance(item, dict) or set(item) != {"point_size", "evidence_sha256"} or type(item["point_size"]) is not int:
        raise BulkError("invalid_generator", "Expected exact captured size/evidence per generated value")
    measurement = dict(value["layout"]["measurement"], **item, text=text)
    value["layout"]["measurement"] = measurement
    value["composer"]["font_size"] = item["point_size"]


def award_years(base, parameters):
    required = {"start", "stop", "step", "directory", "measurements"}
    if set(parameters) != required or any(type(parameters[key]) is not int for key in ("start", "stop", "step")):
        raise BulkError("invalid_generator", "Year series requires explicit bounded integer range and measurements")
    start, stop, step = (parameters[key] for key in ("start", "stop", "step"))
    if not 1000 <= start < stop <= 3000 or step not in {1, 10}:
        raise BulkError("invalid_generator", "Year range is outside the reviewed safety bounds")
    values = [str(year) for year in range(start, stop, step)]
    if set(parameters["measurements"]) != set(values):
        raise BulkError("invalid_generator", "Every generated value requires its own captured fitting evidence")
    for year in values:
        value = _child(base, year + ".jpg", parameters["directory"])
        if value["caption"]["mode"] == "shared":
            value["caption"]["text"] = year
            text = year
        else:
            value["caption"]["suffix"] = " " + year
            # Bind unchanged English fitting. A changed translation must obtain
            # new evidence; complete multilingual fitting belongs to Package D.
            original = base.data["layout"]["measurement"]["text"]
            text = original.rsplit(" ", 1)[0] + " " + year
        _measurement(value, parameters["measurements"][year], text)
        yield Definition.create(value)


def best_of_years(base, parameters):
    required = {"start", "stop", "step", "directory", "measurements", "parent_directory"}
    if set(parameters) != required:
        raise BulkError("invalid_generator", "Best Of requires a year range and explicit parent directory")
    relative_path(parameters["parent_directory"])
    # Reuse range validation, but preserve the translated shared Best Of caption.
    temporary = base.data
    temporary["caption"] = dict(temporary["caption"], mode="shared", key=None, template_key=None, text=str(parameters["start"]))
    for child in award_years(Definition.create(temporary), {key: item for key, item in parameters.items() if key != "parent_directory"}):
        value = child.data
        value["caption"] = base.data["caption"]
        value["layout"]["measurement"]["text"] = base.data["layout"]["measurement"]["text"]
        parent = parameters["parent_directory"] + "/" + value["output"]["filename"]
        value["dependencies"] = [{"poster_id": poster_id(value["category"], parent), "input": "logo"}]
        value["composer"]["logo"] = "defaults-en/" + parent
        yield Definition.create(value)


def separator_variants(base, parameters):
    if set(parameters) != {"variants", "filename"} or not isinstance(parameters["variants"], list) or not 1 <= len(parameters["variants"]) <= 64:
        raise BulkError("invalid_generator", "Separators require bounded explicit named variants")
    seen = set()
    for item in parameters["variants"]:
        if not isinstance(item, dict) or set(item) != {"name", "base_color", "evidence_sha256"} or item["name"] in seen or not re.fullmatch(r"[a-z][a-z0-9-]*", item["name"]):
            raise BulkError("invalid_generator", "Separator variant names/fields must be explicit and unique")
        seen.add(item["name"])
        value = _child(base, parameters["filename"], "separators/" + item["name"])
        value["composer"]["base_color"] = normalize_hex(item["base_color"])
        value["composer"]["logo"] = "@base/" + item["name"] + ".png"
        value["layout"]["measurement"]["evidence_sha256"] = item["evidence_sha256"]
        yield Definition.create(value)


def content_rating_series(base, parameters):
    if set(parameters) != {"values", "directory", "caption_suffix", "measurements"} or parameters["caption_suffix"] not in {"", "+"}:
        raise BulkError("invalid_generator", "Content rating series requires explicit bounded codes and fitting evidence")
    codes = parameters["values"]
    if not isinstance(codes, list) or not 1 <= len(codes) <= 64 or any(not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9+-]{1,12}", code) for code in codes) or len(set(codes)) != len(codes) or set(parameters["measurements"]) != set(codes):
        raise BulkError("invalid_generator", "Content rating codes require unique portable identities and exact measurement coverage")
    prefix = base.data["layout"]["measurement"]["text"].rsplit(" ", 1)[0]
    for code in codes:
        value = _child(base, code + ".jpg", parameters["directory"])
        suffix = " " + code + parameters["caption_suffix"]
        value["caption"]["suffix"] = suffix
        _measurement(value, parameters["measurements"][code], prefix + suffix)
        yield Definition.create(value)


GENERATORS = {("award-years", 1): award_years, ("best-of-years", 1): best_of_years,
              ("separator-variants", 1): separator_variants, ("content-rating-series", 1): content_rating_series}
