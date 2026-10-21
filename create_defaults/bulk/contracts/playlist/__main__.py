"""Explicit pins, stdout report only. No image, state, or remote writes."""

import argparse
import json

from ...common import BulkError
from .validation import PlaylistBoundary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--registry-sha256", required=True)
    parser.add_argument("--adoption-sha256", required=True)
    args = parser.parse_args()
    try:
        result = PlaylistBoundary.load(contract_sha256=args.contract_sha256,
                                       registry_sha256=args.registry_sha256,
                                       adoption_sha256=args.adoption_sha256).audit()
    except (BulkError, OSError) as error:
        result = {"compatible": False, "code": getattr(error, "code", "playlist_source_io"),
                  "details": str(error), "production_enforcement": False, "publication_authorized": False}
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["compatible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
