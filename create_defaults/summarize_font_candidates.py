"""Summarize local official font comparisons with exact glyph/kerning measurements."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path

try:
    from .compare_bebas_fonts import font_metrics
    from .create_poster import digest
except ImportError:
    from compare_bebas_fonts import font_metrics
    from create_poster import digest


def summarize(directory):
    results = json.loads((directory / "results.json").read_text())
    if len(results) != 22:
        raise ValueError("All 22 affected comparisons must finish before summarizing")
    groups = defaultdict(list)
    for result in results:
        variants = result["variants"]
        glyph_metrics = {}
        for name in ("original", "candidate"):
            variant = variants[name]
            path = Path(variant["parameters"]["font"])
            if digest(path) != result[name]["sha256"] or variant["isolated_font_sha256"] != result[name]["sha256"]:
                raise ValueError("Comparison font-byte evidence mismatch")
            glyph_metrics[name] = font_metrics(path, result["text"], variant["parameters"]["font_size"])
        a, b = variants["original"], variants["candidate"]
        delta = lambda key: [right - left for left, right in zip(a["caption"]["legacy"][key], b["caption"]["legacy"][key])]
        entry = {"id": result["id"], "text": result["text"], "category": result["category"], "definition_line": result["definition_line"],
                 "original_sha256": result["original"]["sha256"], "candidate_sha256": result["candidate"]["sha256"],
                 "original_point_size": a["parameters"]["font_size"], "candidate_point_size": b["parameters"]["font_size"],
                 "centered_ink_bound_deltas_candidate_minus_original": delta("centered_ink_bounds"),
                 "original_lines": a["caption"]["python"]["lines"], "candidate_lines": b["caption"]["python"]["lines"],
                 "original_line_widths": a["caption"]["python"]["line_widths"], "candidate_line_widths": b["caption"]["python"]["line_widths"],
                 "glyph_metrics": glyph_metrics,
                 "fixed_size_metrics": {name: variants[name]["fixed_definition_size_metrics"] for name in ("original", "candidate")},
                 "comparison": result["comparison"]}
        family = result["original"]["names"]["1"][0]
        groups[family].append(entry)
    output = {"approval": "Neither candidate applied. Explicit user disposition required; old exact releases remain unverified.", "families": {}}
    for family, rows in groups.items():
        output["families"][family] = {"definitions": len(rows),
            "maximum_rgb_mae": max(row["comparison"]["mean_absolute_error_0_255"] for row in rows),
            "minimum_global_ssim": min(row["comparison"]["global_luminance_ssim_400x600"] for row in rows),
            "all_point_sizes_identical": all(row["original_point_size"] == row["candidate_point_size"] for row in rows),
            "all_line_breaks_identical": all(row["original_lines"] == row["candidate_lines"] for row in rows),
            "maximum_absolute_ink_bound_delta": max(abs(value) for row in rows for value in row["centered_ink_bound_deltas_candidate_minus_original"]),
            "rows": rows}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = summarize(args.report)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=True), encoding="utf-8")
    print(json.dumps({key: {name: value for name, value in group.items() if name != "rows"} for key, group in result["families"].items()}, indent=2))


if __name__ == "__main__":
    main()
