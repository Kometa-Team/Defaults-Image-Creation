"""Build a compact, read-only review of newly flagged comparison patterns."""

import argparse
from collections import defaultdict
import html
import json
import os
from pathlib import Path
from datetime import datetime, timezone

try:
    from .compare_poster_renderers import page
    from .create_poster import ROOT, digest
    from .validation_review import review_summary
except ImportError:
    from compare_poster_renderers import page
    from create_poster import ROOT, digest
    from validation_review import review_summary


def warning_rank(result):
    comparison = result.get("comparisons", {}).get("A-legacy-python", {})
    mae = comparison.get("mean_absolute_error_0_255")
    ssim = comparison.get("global_luminance_ssim_400x600")
    alpha = comparison.get("mean_absolute_alpha_error_0_255")
    ratios = [0.0]
    if mae is not None:
        ratios.append(mae / 1.5)
    if ssim is not None:
        ratios.append(max(0.0, 1 + (.995 - ssim) / .005))
    if alpha is not None:
        ratios.append(alpha / 1.5)
    edges = result.get("caption_diagnostics", {}).get("ink_bound_deltas_python_minus_legacy")
    return {"score": max(ratios), "mae": mae, "ssim": ssim,
            "edge": max(map(abs, edges)) if edges else None}


SORT_SCRIPT = """
const controls = ['sort', 'category', 'font', 'scope'].map(id => document.getElementById(id));
const tbody = document.querySelector('#warning-table tbody');
const rows = [...tbody.rows];
function updateWarnings() {
  const [sort, category, font, scope] = controls.map(control => control.value);
  rows.sort((a, b) => {
    const direction = sort === 'ssim' ? 1 : -1;
    return direction * (Number(a.dataset[sort]) - Number(b.dataset[sort])) || a.dataset.id.localeCompare(b.dataset.id);
  });
  let shown = 0;
  for (const row of rows) {
    row.hidden = (category && row.dataset.category !== category) || (font && row.dataset.font !== font) || (scope && row.dataset.scope !== scope);
    if (!row.hidden) shown++;
    tbody.append(row);
  }
  document.getElementById('warning-count').textContent = `${shown} of ${rows.length} warnings shown`;
}
controls.forEach(control => control.addEventListener('change', updateWarnings));
updateWarnings();
"""


def write_ranked_warnings(root, results):
    rows = sorted((row for row in results if row.get("status") == "warning"),
                  key=lambda row: (-warning_rank(row)["score"], row["id"]))
    body = '<h1>Warnings: Worst First</h1><p><a href="index.html">Complete dashboard</a> | <a href="review-groups.html">Grouped new comparisons</a></p>'
    body += f'<p>{len(rows):,} warnings in a snapshot of {len(results):,} completed records. Automatic numerical ranking is not a confirmed defect or visual approval.</p>'
    body += '<p>Larger threshold ratios appear first. Ranking compares fresh PowerShell against Python, not intentional font changes against older published artwork.</p>'
    body += '<details><summary>Ranking and measurement details</summary><p>The threshold ratio is the largest of RGB error / 1.5, (1 - similarity) / 0.005, and alpha error / 1.5 when available. Higher is further beyond the existing screen; over 1 exceeds a cutoff. Text shift measures isolated caption edges, not overall layout. Missing measurements are shown as n/a.</p></details>'
    body += '<div style="display:flex;flex-wrap:wrap;gap:16px;margin:16px 0">'
    choices = {
        "sort": [("score", "Worst numerical difference"), ("ssim", "Lowest similarity first"),
                 ("mae", "Largest RGB difference first"), ("edge", "Largest text-edge shift first")],
        "category": [("", "All categories")] + [(value, value) for value in sorted({row["category"] for row in rows})],
        "font": [("", "All fonts")] + [(value, value) for value in sorted({", ".join(row["font"]["family"]) for row in rows})],
        "scope": [("", "All completed warnings"), ("new", "New since checkpoint"), ("checkpoint", "Imported checkpoint")],
    }
    for name, options in choices.items():
        body += '<label>' + name.title() + ' <select id="' + name + '">'
        body += ''.join('<option value="' + html.escape(value, quote=True) + '">' + html.escape(label) + '</option>' for value, label in options)
        body += '</select></label>'
    body += '</div><p id="warning-count" aria-live="polite"></p><div style="overflow-x:auto"><table id="warning-table" style="min-width:850px"><thead><tr>'
    body += ''.join('<th scope="col">' + label + '</th>' for label in
                    ("Poster / Category", "Font", "Threshold Ratio", "RGB Difference / 255", "Similarity", "Text Shift (px)", "Source"))
    body += '</tr></thead><tbody>'
    records = []
    for result in rows:
        rank = warning_rank(result)
        scope = "checkpoint" if result.get("checkpoint_origin") else "new"
        font = ", ".join(result["font"]["family"])
        attributes = {"id": result["id"], "category": result["category"], "font": font, "scope": scope,
                      "score": rank["score"], "mae": rank["mae"] if rank["mae"] is not None else -1,
                      "ssim": rank["ssim"] if rank["ssim"] is not None else 2,
                      "edge": rank["edge"] if rank["edge"] is not None else -1}
        body += '<tr ' + ' '.join('data-' + key + '="' + html.escape(str(value), quote=True) + '"' for key, value in attributes.items()) + '>'
        name = result["parameters"].get("out_name") or result["id"]
        caption = result["parameters"].get("text") or name
        body += '<td><a href="cases/' + html.escape(result["id"], quote=True) + '/index.html">' + html.escape(caption) + '</a><br><small>' + html.escape(result["category"] + ': ' + name) + '</small></td>'
        body += '<td>' + html.escape(font) + '</td><td>' + f'{rank["score"]:.3f}' + '</td>'
        for metric, precision in (("mae", 4), ("ssim", 6), ("edge", 0)):
            value = rank[metric]
            body += '<td>' + (f'{value:.{precision}f}' if value is not None else 'n/a') + '</td>'
        body += '<td>' + ("Imported checkpoint" if scope == "checkpoint" else "New") + '</td></tr>'
        records.append({"id": result["id"], "scope": scope, **rank})
    body += '</tbody></table></div><script>' + SORT_SCRIPT + '</script>'
    (root / "warnings-ranked.html").write_text(page("Warnings: Worst First", body), encoding="utf-8")
    (root / "warnings-ranked.json").write_text(json.dumps({"warnings": records,
        "scope": "Fresh PowerShell versus Python; presentation only; original result records unchanged"}, indent=2), encoding="utf-8")


def warning_groups(results):
    groups = defaultdict(list)
    for result in results:
        if result.get("checkpoint_origin") or result.get("status") != "warning":
            continue
        parameters = dict(result["parameters"])
        for key in ("base_color", "logo", "out_name"):
            parameters.pop(key, None)
        key = json.dumps({"category": result["category"], "font_sha256": result["font"]["sha256"],
                          "parameters": parameters}, sort_keys=True)
        groups[key].append(result)
    return sorted(groups.values(), key=lambda rows: (-max(warning_rank(row)["score"] for row in rows),
                                                    rows[0]["category"], rows[0]["parameters"].get("text", "")))


def write_groups(root, results):
    groups = warning_groups(results)
    count = sum(map(len, groups))
    body = f'<h1>New Comparison Warnings</h1><p>{count:,} newly flagged jobs in {len(groups):,} review groups. Imported checkpoint warnings are not repeated here.</p>'
    body += f'<p>Snapshot of {len(results):,} completed job records. This is not full-batch completion unless all 9,958 jobs are present.</p>'
    body += '<p>Groups share a caption, font and rendering parameters; colors and source artwork may vary. Each variant remains independently measured and flagged in the full report. One sample is not a claim that every variant was visually inspected.</p>'
    body += '<p><a href="warnings-ranked.html">All warnings, sortable worst first</a> | <a href="index.html">Complete job dashboard and font coverage</a></p>'
    records = []
    for rows in groups:
        sample = max(rows, key=lambda result: warning_rank(result)["score"])
        prefix = "cases/" + sample["id"] + "/"
        text = sample["parameters"].get("text") or sample["id"]
        body += '<section><h2>' + html.escape(text) + '</h2>'
        body += f'<p>{len(rows)} flagged variant(s); {html.escape(sample["category"])}; {html.escape(", ".join(sample["font"]["family"]))}; {sample["parameters"]["font_size"]} points.</p>'
        body += '<p>Groups and samples are ranked by the largest fresh-engine difference relative to the existing comparison thresholds. Source artwork outside the caption still needs its own visual review.</p>'
        body += '<div class="images">'
        for engine, label in (("legacy", "PowerShell reference"), ("python", "Python candidate")):
            preview = prefix + engine + "-preview.jpg"
            full = prefix + engine + ".jpg"
            if (root / preview).is_file():
                target = full if (root / full).is_file() else preview
                body += f'<figure><figcaption>{label}</figcaption><a href="{target}"><img loading="lazy" src="{preview}" alt="{label}"></a></figure>'
        body += '</div>' + review_summary(sample)
        comparison = sample["comparisons"].get("A-legacy-python", {})
        body += '<div class="images">'
        for index, filename in enumerate(comparison.get("text_crops", [])):
            source = prefix + filename
            body += f'<figure><figcaption>{"PowerShell" if index == 0 else "Python"} text crop</figcaption><img loading="lazy" src="{html.escape(source)}" alt="Caption crop"></figure>'
        body += '</div><p><a href="' + prefix + 'index.html">Sample: full individual evidence</a></p>'
        body += '<details><summary>All flagged variants in this group</summary><ul>'
        for row in rows:
            body += '<li><a href="cases/' + row["id"] + '/index.html">' + html.escape(row["parameters"]["out_name"]) + '</a></li>'
        body += '</ul></details></section>'
        records.append({"category": sample["category"], "caption": text, "sample": sample["id"],
                        "count": len(rows), "job_ids": [row["id"] for row in rows]})
    body += '<p>Grouping changes presentation only. Numerical metrics, warning statuses and original evidence are not rewritten.</p>'
    (root / "review-groups.html").write_text(page("New Comparison Warnings", body), encoding="utf-8")
    record = {"new_warning_jobs": count, "groups": records, "generator_sha256": digest(Path(__file__)),
              "completed_job_records": len(results), "generated_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Presentation only; no new user approval inferred"}
    (root / "review-groups.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    write_ranked_warnings(root, results)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", required=True, type=Path)
    parser.add_argument("--published-repo", type=Path, default=os.environ.get("DEFAULT_IMAGES_LOCAL_REPO"))
    args = parser.parse_args()
    root = args.report_dir.resolve()
    if root == ROOT or root.is_relative_to(ROOT):
        parser.error("Report must be outside production assets")
    if args.published_repo:
        published = args.published_repo.resolve()
        if root == published or root.is_relative_to(published) or published.is_relative_to(root):
            parser.error("Report and read-only published checkout must be disjoint")
    if not (root / "run.json").is_file() or not (root / "manifest.json.gz").is_file():
        parser.error("Existing batch report required")
    results = [json.loads(path.read_text()) for path in (root / "cases").glob("*/result.json")]
    record = write_groups(root, results)
    print(f'{record["new_warning_jobs"]} new warning jobs in {len(record["groups"])} review groups')


if __name__ == "__main__":
    main()
