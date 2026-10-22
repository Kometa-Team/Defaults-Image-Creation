"""Confirmed D09 policies and measured Phase 1 source classifications.

Never guess from another category, a source count, or a white directory name.
"""

from pathlib import PurePosixPath

from ...common import BulkError


WHITE_DEFAULTS = {"Playlist", "Franchise", "Genre", "Seasonal", "Universe"}
PAIRED = {"Chart", "Country", "Network", "Streaming"}
ICON_WHITE = {"Aspect", "Awards", "ContentRating", "Resolution"}
TEXT = {"AudioLanguage", "Based", "SubtitleLanguage"}
ERA = {"Year", "Decade"}


def source_kind(record):
    value = record.to_dict() if hasattr(record,"to_dict") else record
    category,source = value["identity"]["category"],value["identity"]["source"]["path"]
    if category == "Overlays":
        return "overlay_source"
    if source == "transparent.png":
        return "placeholder"
    if value["source_kind"] == "generated_parent" or category == "Separators" and source.startswith("@base/"):
        return "composition"
    return "logo"


def treatment(category,kind):
    if category == "Overlays":
        return "SOURCE_PRESERVING"
    if kind == "placeholder":
        return "NOT_APPLICABLE"
    if category in ERA or kind == "composition":
        return "SPECIAL"
    if category in WHITE_DEFAULTS or category in ICON_WHITE or category == "Separators":
        return "WHITE_ONLY"
    if category in PAIRED:
        return "BOTH_REQUIRED"
    if category in {"Studio","VideoFormat"}:
        return "SOURCE_PRESERVING"
    raise BulkError("category_policy","No approved source treatment for this category/variant")


def presentation(value,job):
    category=value["identity"]["category"]
    if category == "Overlays":
        return job["variant"]
    if category in PAIRED:
        parts=PurePosixPath(value["identity"]["public_path"]).parts
        if len(parts)>=3 and parts[1] in {"white","color"}:
            return parts[1]
        raise BulkError("category_pair_mapping","Paired category lacks an explicit accepted presentation path")
    return "single"


def companions(values):
    """Exact existing paths, including the six Country/four Network text outputs.

    This preserves already present output membership; it never infers artwork
    from source counts or creates an extra overlay group.
    """
    result={v["identity"]["id"]:[] for v in values}
    groups={}
    for value in values:
        item=value["identity"];category=item["category"]
        if category in PAIRED:
            parts=PurePosixPath(item["public_path"]).parts
            if len(parts)<3 or parts[1] not in {"white","color"}:
                raise BulkError("category_pair_mapping","Unexpected accepted pair destination")
            key=(category,"/".join(parts[2:]));role=parts[1]
        elif category == "Overlays":
            # Same source can legitimately appear in distinct branches; the
            # branch is part of the accepted exact destination.
            path=PurePosixPath(item["public_path"])
            role=path.parent.name
            key=(category,str(path.parent.parent),item["source"]["path"])
        else:
            continue
        if role in groups.setdefault(key,{}):
            raise BulkError("category_duplicate_variant","Duplicate required presentation")
        groups[key][role]=item["id"]
    for key,members in groups.items():
        expected={"standard","bigger"} if key[0] == "Overlays" else {"white","color"}
        if set(members)!=expected:
            raise BulkError("category_missing_variant","Incomplete historical required membership: "+str(key))
        ids=sorted(members.values())
        for identity in ids:
            result[identity]=[i for i in ids if i!=identity]
    # Preserve every already M2-pinned real-logo companion without rewriting it.
    for value in values:
        pair=value["paired_identity"]
        if pair is not None and pair not in result[value["identity"]["id"]]:
            raise BulkError("category_pair_substitution","M6 membership contradicts an accepted M2 pair")
    return result
