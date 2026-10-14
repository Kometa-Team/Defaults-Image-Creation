"""Opt-in browser check of an actual generated, self-contained report."""
import csv
import json
import os
from pathlib import Path

import pytest
from PIL import Image, ImageStat


def test_local_report_images_filters_zoom_and_persistent_review_exports(tmp_path):
    report = os.getenv("BACKGROUND_REPORT_SMOKE")
    if not report:
        pytest.skip("Set BACKGROUND_REPORT_SMOKE to a generated comparison.html")
    playwright = pytest.importorskip("playwright.sync_api")
    errors = []
    with playwright.sync_playwright() as runtime:
        launch = {"headless": True}
        if os.getenv("BACKGROUND_REPORT_BROWSER"):
            launch["executable_path"] = os.environ["BACKGROUND_REPORT_BROWSER"]
        browser = runtime.chromium.launch(**launch)
        try:
            context = browser.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
            context.set_default_timeout(120000)
            context.set_default_navigation_timeout(180000)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(Path(report).resolve().as_uri(), wait_until="load")
            count = page.locator("#samples section").count()
            assert count > 0
            for portrait in page.locator("#samples section").all():
                portrait.scroll_into_view_if_needed()
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_function("Array.from(document.querySelectorAll('#samples img')).every(i => i.complete && i.naturalWidth > 0)")
            assert page.locator("#samples img").count() >= count * 2
            page.locator("#model").select_option("birefnet-portrait")
            assert page.locator("#samples figure").count() == count * 2
            for background in ("checker", "white", "black", "kometa"):
                page.locator("#background").select_option(background)
                assert page.locator("#samples").get_attribute("class") == background
            page.locator("#samples img").first.click()
            assert page.locator("#full").is_visible()
            assert page.locator("#fullImage").evaluate("image => image.naturalWidth") > 0
            page.locator("#close").click()
            page.locator("#flag").select_option("unverified")
            assert page.locator("#samples section").count() == count
            choice = page.locator(".review select").first
            choice.select_option("Needs review")
            page.locator(".review textarea").first.fill('Browser test, "quoted" note\nsecond line')
            with page.expect_download() as exported:
                page.locator("#jsonExport").click()
            json_path = tmp_path / "reviews.json"
            exported.value.save_as(json_path)
            data = json.loads(json_path.read_text(encoding="utf-8"))
            assert sum(r["result"] == "Needs review" for r in data["reviews"]) == 1
            assert data["aggregates"]["source-unverified"]["actually_reviewed"] == 1
            assert all(engine["wins"] == 0 for engine in data["aggregates"]["source-unverified"]["engines"].values())
            with page.expect_download() as exported:
                page.locator("#csvExport").click()
            csv_path = tmp_path / "reviews.csv"
            exported.value.save_as(csv_path)
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            assert rows[0]["notes"] == 'Browser test, "quoted" note\nsecond line'
            page.reload(wait_until="load")
            assert page.locator(".review select").first.input_value() == "Needs review"
            page.locator(".review select").first.select_option("")
            page.locator("#import").set_input_files(csv_path)
            page.wait_for_function("document.querySelector('.review select').value === 'Needs review'")
            page.locator("#import").set_input_files(json_path)
            page.locator("#background").select_option("white")
            for name, viewport in (("desktop", {"width": 1440, "height": 1000}),
                                   ("mobile", {"width": 390, "height": 844})):
                page.set_viewport_size(viewport)
                page.screenshot(path=str(tmp_path / f"{name}.png"))
                assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                with Image.open(tmp_path / f"{name}.png") as screenshot:
                    assert max(ImageStat.Stat(screenshot.convert("RGB")).stddev) > 10
            assert not errors, errors
        finally:
            browser.close()
