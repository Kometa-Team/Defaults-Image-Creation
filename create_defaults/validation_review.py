"""Human-readable explanations for offline image comparison screens."""

import html


def review_summary(result):
    comparisons = result.get("comparisons", {})
    content = '<section><h2>What Was Flagged</h2>'
    if result.get("status") == "failure":
        content += '<p>A required render or validation step failed. This is not just a visual-similarity warning.</p>'
        content += '<ul>' + ''.join('<li>' + html.escape(note) + '</li>' for note in result.get("notes", [])) + '</ul>'
    titles = {"A": "Fresh PowerShell versus Python", "B": "Fresh PowerShell versus published artwork",
              "C": "Python versus published artwork"}
    flagged = False
    for label, comparison in comparisons.items():
        if not comparison.get("flag_for_review") and comparison.get("comparable") is not False:
            continue
        flagged = True
        title = titles.get(label[0], label)
        content += '<h3>' + html.escape(title) + '</h3><ul>'
        if not comparison.get("comparable"):
            content += '<li>The images could not be compared on the same canvas. Check dimensions and missing outputs.</li>'
        else:
            mae = comparison.get("mean_absolute_error_0_255")
            ssim = comparison.get("global_luminance_ssim_400x600")
            alpha = comparison.get("mean_absolute_alpha_error_0_255")
            if mae is not None:
                decision = "above" if mae > 1.5 else "within"
                content += f'<li>Average RGB channel difference: {mae:.3f} out of 255, {decision} the 1.500 cutoff.</li>'
            if ssim is not None:
                decision = "below the 0.995 cutoff, triggering a warning" if ssim < .995 else "within the 0.995 cutoff"
                content += f'<li>Global similarity score: {ssim:.6f}, {decision}. This whole-image screen can react to small letter-edge differences.</li>'
            if alpha is not None and alpha > 1.5:
                content += f'<li>Average transparency difference: {alpha:.3f} out of 255, above the 1.500 cutoff.</li>'
            p99 = comparison.get("channel_difference_p99_0_255")
            if p99 is not None:
                content += f'<li>99% of red, green and blue channel differences are {p99} out of 255 or less.</li>'
        content += '</ul>'
    if not flagged and result.get("status") != "failure":
        content += '<p>No numerical comparison cutoff was exceeded. Any remaining warning concerns the notes or missing comparison evidence, not a measured visible defect.</p>'
    delta = result.get("caption_diagnostics", {}).get("ink_bound_deltas_python_minus_legacy")
    if delta:
        largest = max(abs(value) for value in delta)
        content += f'<p>Largest isolated text-boundary shift: <strong>{largest} pixel(s)</strong>. This measures caption edges, not the entire poster layout.</p>'
    if flagged:
        content += '<h3>What To Look For</h3><p>Compare the wording, line breaks, letter spacing, text size and centering, logo position, colors, borders and clipped content. The text crops below make small text differences easier to inspect.</p>'
        content += '<p>A warning is an automatic review request, not a confirmed defect. If the posters look the same, faint outlines in an amplified difference image may just be font smoothing or JPEG encoding. Amplification exaggerates those differences; it is not the normal poster appearance.</p>'
    return content + '</section>'
