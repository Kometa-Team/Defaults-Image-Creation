"""Explicit configuration and compatibility selectors; no network or installation."""

from dataclasses import dataclass, fields
import os
from pathlib import Path
import re

from .common import BulkError, load_yaml, reject_links


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("ar", "en", "da", "de", "es", "fr", "it", "nb_NO", "nl", "pt-br", "sv")
CATEGORIES = ("Aspect", "AudioLanguage", "Awards", "Based", "Chart", "ContentRating", "Country", "Decade", "Franchise", "Genre", "Network", "Playlist", "Resolution", "Seasonal", "Separators", "Streaming", "Studio", "SubtitleLanguage", "Universe", "VideoFormat", "Year", "Overlays")
ALIASES = {name.casefold(): name for name in CATEGORIES}
ALIASES.update({name.casefold(): category for category, names in {
    "AudioLanguage": ["AudioLanguages"], "Awards": ["Award"], "Chart": ["Charts"],
    "ContentRating": ["ContentRatings"], "Country": ["Countries"], "Decade": ["Decades"],
    "Franchise": ["Franchises"], "Genre": ["Genres"], "Network": ["Networks"],
    "Overlays": ["Overlay"], "Playlist": ["Playlists"], "Resolution": ["Resolutions"],
    "Seasonal": ["Seasonals"], "Separators": ["Separator"], "Studio": ["Studios"],
    "SubtitleLanguage": ["SubtitleLanguages"], "Universe": ["Universes"],
    "VideoFormat": ["VideoFormats"], "Year": ["Years"],
}.items() for name in names})


def select_categories(values):
    result = []
    for value in values:
        if value.casefold() == "all":
            result.extend(CATEGORIES)
        elif value.casefold() in ALIASES:
            result.append(ALIASES[value.casefold()])
        else:
            raise BulkError("unknown_category", f"Unknown category: {value}")
    return tuple(dict.fromkeys(result))


def language_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z]{2,3}(?:[-_][A-Za-z0-9]{2,8}){0,2}", value):
        raise BulkError("unknown_language", "Unsafe or malformed exact language identifier")
    return value


def select_languages(values, *, available=None):
    for value in values:
        language_id(value)
        if value not in (LANGUAGES if available is None else available):
            raise BulkError("unknown_language", "Language identifier absent from the selected registry; aliases require explicit mappings")
    return tuple(dict.fromkeys(values))


def repository(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]+", value) or value.split("/")[1] in {".", ".."}:
        raise BulkError("invalid_repository", "Expected an explicit owner/repository")
    return value


def branch_name(value):
    if not isinstance(value, str) or not value or value.startswith(("-", "/", ".")) or value.endswith(("/", ".", ".lock")) or ".." in value or "@{" in value or any(c.isspace() or ord(c) < 32 or c in '~^:?*[\\%' for c in value) or any(part in {"", ".", ".."} for part in value.split("/")):
        raise BulkError("invalid_branch", "Unsafe branch identifier")
    return value


@dataclass(frozen=True)
class Config:
    asset_dir: Path = ROOT
    cache_dir: Path = ROOT.parent / "config/bulk/cache"
    workspace_dir: Path = ROOT.parent / "config/bulk/workspaces"
    output_dir: Path = ROOT.parent / "config/bulk/output"
    translation_dir: Path = ROOT / "fixtures/english"
    github_repository: str = "Kometa-Team/Default-Images"
    github_branch: str = "master"
    offline: bool = False
    remote_ttl: int = 3600
    max_blob_bytes: int = 20_000_000

    def __post_init__(self):
        for name in ("asset_dir", "cache_dir", "workspace_dir", "output_dir", "translation_dir"):
            object.__setattr__(self, name, reject_links(getattr(self, name)).resolve())
        repository(self.github_repository)
        branch_name(self.github_branch)
        if type(self.offline) is not bool or any(type(value) is not int or value < 1 for value in (self.remote_ttl, self.max_blob_bytes)):
            raise BulkError("invalid_config", "Invalid boolean or numeric configuration")
        for name in ("cache_dir", "workspace_dir", "output_dir"):
            target = getattr(self, name)
            if target.is_relative_to(self.asset_dir) or self.asset_dir.is_relative_to(target):
                raise BulkError("unsafe_workspace", "Writable state must be separate from source artwork")
        writable = (self.cache_dir, self.workspace_dir, self.output_dir)
        if any(a == b or a.is_relative_to(b) or b.is_relative_to(a) for index, a in enumerate(writable) for b in writable[index + 1:]):
            raise BulkError("unsafe_workspace", "Cache, output and temporary workspace roots must be isolated")

    @classmethod
    def load(cls, *, file=None, environment=None, **explicit):
        environment = os.environ if environment is None else environment
        names = {field.name for field in fields(cls)}
        values = {}
        for name in names:
            key = "DEFAULTS_" + name.upper()
            if key in environment:
                values[name] = environment[key]
        for name in ("remote_ttl", "max_blob_bytes"):
            if name in values:
                try:
                    values[name] = int(values[name])
                except ValueError as error:
                    raise BulkError("invalid_config", f"Invalid {name}") from error
        if "offline" in values:
            if values["offline"].lower() not in {"true", "false"}:
                raise BulkError("invalid_config", "DEFAULTS_OFFLINE must be true or false")
            values["offline"] = values["offline"].lower() == "true"
        if file is not None:
            data = load_yaml(file)
            if not isinstance(data, dict) or set(data) - names:
                raise BulkError("invalid_config", "Unknown configuration field")
            values.update(data)
        if set(explicit) - names:
            raise BulkError("invalid_config", "Unknown explicit configuration field")
        values.update({key: value for key, value in explicit.items() if value is not None})
        return cls(**values)
