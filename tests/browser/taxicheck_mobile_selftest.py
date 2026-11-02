"""Offline browser smoke for ?qa=run on the PUBLIC synthetic TaxiCheck mockup.

The page is served from local files. Nothing is published, and no real financial
system, Google Apps Script, or authentication service is called.
"""
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "index.html"
JS = ROOT / "qa" / "mobile-selftest.js"
ADVANCED = ROOT / "qa" / "advanced-suite.js"


def check_sources():
    src = JS.read_text(encoding="utf8")
    html = HTML.read_text(encoding="utf8")
    assert 'src="qa/mobile-selftest.js" defer' in html
    assert 'src="qa/advanced-suite.js" defer' in html
    advanced = ADVANCED.read_text(encoding="utf8")
    assert "qa_fixture=1" in advanced and "iframe" in advanced
    assert "google.script.run" not in advanced
    assert "fetch(" not in advanced and "XMLHttpRequest" not in advanced
    assert "get('qa') !== 'run'" in src, "Self-test must be opt-in"
    assert "localStorage.setItem(" not in src, "Tests must not write QA or financial state"
    assert "fetch(" not in src, "No network calls from QA controller"
    assert "google.script.run" not in src
    assert "submitQuickEntry(" not in src
    assert "saveEntry(" not in src
    assert "resetDemo" not in src


def smoke(browser, browser_name, viewport, base):
    context = browser.new_context(
        viewport={"width": viewport, "height": 815},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        color_scheme="dark",
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    unsafe = []
    page.on("request", lambda req: unsafe.append((req.method, req.url))
            if req.method != "GET" else None)
    try:
        page.goto(base, wait_until="load")
        assert page.locator("#tcAutoQa").count() == 0, "QA overlay leaked to normal demo"
        assert page.locator("#homeCashValue").inner_text().strip() not in ("", "—")
        original_cash = page.locator("#homeCashValue").inner_text().strip()
        original_net = page.locator("#homeNetValue").inner_text().strip()
        page.goto(base + "?qa=run", wait_until="load")
        page.wait_for_function(
            "() => window.TaxiCheckQaLastReport?.complete === true", timeout=60000
        )
        report = page.evaluate("window.TaxiCheckQaLastReport")
        assert report["total"] >= 40, report
        assert page.locator("#tcQaResults li").count() == report["total"]
        screenshots = Path(os.environ.get("TAXICHECK_QA_ARTIFACT_DIR", "playwright-artifacts/mobile-selftest"))
        screenshots.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshots / f"{browser_name}-{viewport}-selftest.png"), full_page=True)
        (screenshots / f"{browser_name}-{viewport}-results.json").write_text(json.dumps({
            "engine": browser_name, "viewport": viewport,
            "report": report,
            "checks": page.locator("#tcQaResults li").all_inner_texts()
        }, ensure_ascii=False, indent=2), encoding="utf8")
        assert report["failed"] == 0, (
            f"{browser_name} {viewport}: "
            + page.locator("#tcQaResults").inner_text()
        )
        assert page.locator("#tcQaResults li[data-state=pass]").count() == report["total"]
        assert "Успешно" in page.locator("#tcQaStatus").inner_text()
        assert page.locator('iframe[title="Временный макет для автоматической проверки"]').count() == 0
        assert page.locator("#tcQaCopy").is_enabled()
        assert page.locator("#tcQaShare").is_enabled()
        assert page.locator("#home").is_visible()
        assert page.locator("#homeCashValue").inner_text().strip() == original_cash
        assert page.locator("#homeNetValue").inner_text().strip() == original_net
        assert page.evaluate(
            "document.documentElement.scrollWidth <= window.innerWidth + 3"
        ), "Horizontal overflow"
        assert not unsafe, unsafe
        assert not errors, errors
        # The same one-tap path must be repeatable without changing demo data.
        page.locator("#tcQaAgain").click()
        page.wait_for_function(
            "() => window.TaxiCheckQaLastReport?.complete === true && "
            "!document.querySelector('#tcQaAgain').disabled", timeout=30000
        )
        again = page.evaluate("window.TaxiCheckQaLastReport")
        assert again == report, (report, again)
        assert not errors, errors
        print(f"PASS {browser_name} {viewport}px: {report['total']} checks, repeat, normal demo, GET only")
    finally:
        context.close()


def main():
    check_sources()
    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}/"
    try:
        with sync_playwright() as p:
            for engine in ("chromium", "webkit"):
                browser = getattr(p, engine).launch(headless=True)
                try:
                    for width in (375, 402):
                        smoke(browser, engine, width, base)
                finally:
                    browser.close()
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
