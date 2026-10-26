"""Block publication of unresolved selections, including pre-repair batches."""
import json
from pathlib import Path
import re


class IncompleteBatchError(ValueError):
    pass


def assert_batch_ready(config):
    config = Path(config)
    for name in ("tmdb_people", "remove_bg_birefnet"):
        path = config / "logs" / (name + ".json")
        if path.exists():
            summary = json.loads(path.read_text(encoding="utf8"))
            if (summary.get("exit_code", 0) != 0 or summary.get("failed", 0)
                    or summary.get("outcome") in {"partial_failure", "fatal"}
                    or (name == "tmdb_people" and not summary.get("complete"))):
                raise IncompleteBatchError("Publication blocked: unresolved " + name + " inputs; retry the existing batch")
    manifest_path = config / "manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    if not manifest.get("explicit_people_list"):
        return
    identities_path = config / "tmdb_identities.json"
    identities = json.loads(identities_path.read_text(encoding="utf8")) if identities_path.exists() else {}
    # Legacy TMDB steps returned success on swallowed exceptions. An old done
    # marker alone is not evidence that every explicitly selected person exists.
    from people_remote_inventory import name_key
    receipt_path = config / "logs/tmdb_people.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf8")) if receipt_path.exists() else {}
    no_local_work = {row["input_identifier"] for row in receipt.get("files", [])
                     if row.get("status") in {"already_complete", "not_selected"}}
    required_names = set()
    for filename in ("people_list.txt", "people_overrides.txt"):
        path = config / filename
        if not path.exists():
            continue
        for item in path.read_text(encoding="utf8").splitlines():
            item = item.strip()
            if not item or item.startswith("#") or item in no_local_work:
                continue
            parts = [part.strip() for part in item.split("|") if part.strip()]
            numeric = next((part for part in parts if part.isdigit()), None)
            selected_ids = {row.get("person_id") for row in receipt.get("files", [])
                            if row.get("input_identifier") == item and row.get("status") in {"downloaded", "reused"}}
            alias = parts[1] if len(parts) == 2 and parts[0].isdigit() else parts[2] if len(parts) >= 3 else None
            matched = {name_key(name) for name, person_id in identities.items()
                       if (numeric is None or str(person_id) == numeric)
                       and (alias is None or name_key(name) == name_key(re.sub(r'[\\/:*?"<>|]+', "_", alias)))}
            if numeric is None and selected_ids:
                matched = {name_key(name) for name, person_id in identities.items() if str(person_id) in selected_ids}
            elif numeric is None:
                matched &= {name_key(re.sub(r'[\\/:*?"<>|]+', "_", parts[0]))}
            if not matched:
                raise IncompleteBatchError("Publication blocked: an explicit selection has no successful TMDB identity; retry tmdb for this batch")
            required_names |= matched
    for style in ("bw", "diiivoy", "diiivoycolor", "rainier", "original", "signature", "transparent"):
        rendered = {name_key(path.stem) for path in (config / "people_dirs" / style).glob("*/Images/*")
                    if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}}
        if required_names - rendered:
            raise IncompleteBatchError("Publication blocked: explicit selections lack all seven generated styles; retry local generation")
