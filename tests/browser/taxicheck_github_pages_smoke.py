#!/usr/bin/env python3
"""Read-only public-site Playwright smoke test for the TaxiCheck synthetic demo.

Only the browser's in-memory demonstration forms are changed. This does not
contact Apark, Sheets or the private TaxiCheck application.
"""
import json
import os
import re
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

SITE = os.environ.get(
    "TAXICHECK_PAGES_URL",
    "https://kizer-gpt.github.io/TaxiCheckTestPage/",
)
EXPECTED_HOST = "kizer-gpt.github.io"
if urlparse(SITE).scheme != "https" or urlparse(SITE).hostname != EXPECTED_HOST:
    raise SystemExit("Refusing to run against a URL outside the public demo host")

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "playwright-artifacts"
OUT.mkdir(parents=True, exist_ok=True)
VIEWPORTS = ((402, 874), (375, 812))
EXPECTED_SHIFTS = {
    "s20": ("2026-10-20", "10:00", "2026-10-20", "22:00"),
    "s21": ("2026-10-21", "23:00", "2026-10-22", "13:00"),
    "s22": ("2026-10-22", "14:00", "2026-10-23", "02:00"),
}
CASES = []


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def rubles(label):
    value = re.sub(r"[^\d,.\-−]", "", label).replace("−", "-").replace(",", ".")
    return float(value)


def no_overflow(page, context):
    metrics = page.evaluate("""() => ({
      width: window.innerWidth,
      doc: document.documentElement.scrollWidth,
      body: document.body.scrollWidth
    })""")
    require(
        metrics["doc"] <= metrics["width"] + 1,
        f"Horizontal overflow in {context}: {metrics}",
    )


def assert_shift(page, shift_id, start, start_time, end, end_time):
    chip = page.locator(f'#shiftRibbon [data-shift-id="{shift_id}"]')
    chip.click()
    require(chip.get_attribute("aria-pressed") == "true", "Shift was not selected")
    period = page.locator("#periodLine").inner_text()
    fmt = lambda d: d[8:10] + "." + d[5:7]
    require(
        f"{fmt(start)} {start_time}" in period
        and f"{fmt(end)} {end_time}" in period,
        f"Wrong dates in selected shift: {period}",
    )
    require(
        ("cross-day" in (chip.get_attribute("class") or "")) == (start != end),
        f"Cross-midnight marker incorrect for {shift_id}",
    )
    page.locator("#shiftEditToggle").click()
    expected = {
        "#shiftFromDate": start,
        "#shiftFromTime": start_time,
        "#shiftToDate": end,
        "#shiftToTime": end_time,
    }
    for selector, value in expected.items():
        actual = page.locator(selector).input_value()
        require(actual == value, f"{shift_id} {selector}: {actual} != {value}")
    no_overflow(page, f"{shift_id} shift editor")
    page.locator("#shiftEditCancel").click()
    no_overflow(page, f"{shift_id} dashboard")


def test_one_screen_dashboard(page):
    """Driver-first home: only cash-after-fees, net and quick entry actions."""
    require(page.locator("#home").is_visible(), "Home not visible")
    require(not page.locator("#report").is_visible(), "Old analytics clutter is on the home")
    require(page.locator("#home .home-kpi").count() == 2,
            "Home must only have cash and net KPI cards")
    require(page.locator("#homeCashValue").is_visible()
            and page.locator("#homeNetValue").is_visible(),
            "Two home amounts not visible")
    require(page.locator("#homeCashCaption").inner_text().startswith("После комиссий"),
            "Home cash must represent after-fee earnings")
    require(not page.locator("#quickEntryForm").is_visible(),
            "Quick input should start collapsed")
    require(page.locator('[data-quick="cash"]').is_visible()
            and page.locator('[data-quick="fuel"]').is_visible(),
            "One-tap cash and fuel actions must be available")
    require(page.locator("#sharePreview").is_disabled(), "Share is a clearly disabled placeholder")
    require(page.locator("#shiftEditToggle").is_visible(), "Shift edit shortcut missing")
    require(not page.locator("#shiftEditorPanel").is_visible(),
            "Closed shift editor consumes home space")
    require(page.locator(".shift-chip").count() >= 5,
            "Historical shift selector lost")
    bounds = page.evaluate("""() => {
      const rect = s => document.querySelector(s).getBoundingClientRect();
      return {bottom:rect('#sharePreview').bottom,
        navTop:rect('#bottomNav').top,
        screen:innerHeight,periodHeight:rect('#periodPanel').height,
        netFont:getComputedStyle(document.querySelector('#homeNetValue')).fontSize,
        cashFont:getComputedStyle(document.querySelector('#homeCashValue')).fontSize};
    }""")
    print("MINIMAL_HOME_FIT", page.viewport_size["width"], bounds, flush=True)
    require(bounds["bottom"] < bounds["navTop"]+5,
            f"Minimal home overlaps fixed tab bar: {bounds}")
    require(bounds["periodHeight"] <= 170,
            f"Period switcher must remain compact: {bounds}")
    require(float(bounds["netFont"].replace("px","")) >= 20
            and float(bounds["cashFont"].replace("px","")) >= 20,
            f"Home amounts became illegibly small: {bounds}")
    no_overflow(page, "minimal home")
    page.locator("#modeCustom").click()
    require(page.locator("#customModePanel").is_visible(),
            "Custom period is no longer reachable")
    page.locator("#modeShifts").click()
    page.locator("#shiftEditToggle").click()
    require(page.locator("#shiftEditContent").is_visible(),
            "Shift editing is not reachable")
    page.locator("#shiftEditCancel").click()
    require(not page.locator("#shiftEditorPanel").is_visible(),
            "Shift editor didn't collapse")


def test_first_four_finance_tiles(page):
    """The first four cards have matching title alignment and deliberate hierarchy."""
    cards = page.locator('#tileGrid > .tile')
    require(cards.count() == 8, "Dashboard must retain all eight cards")
    for index, name in enumerate(("Касса", "Комиссии", "Аренда", "Заправки")):
        card = cards.nth(index)
        require("tile-finance" in (card.get_attribute("class") or ""),
                f"{name}: finance card structure absent")
        heading = card.locator(":scope > .tile-finance-heading")
        require(heading.count() == 1 and heading.inner_text() == name,
                f"{name}: title is misplaced")
        require(heading.evaluate("(x) => getComputedStyle(x).borderBottomStyle") == "solid",
                f"{name}: heading separator missing")
        expected_justify = "flex-start" if name == "Заправки" else "space-between"
        require(card.evaluate("(x) => getComputedStyle(x).justifyContent") == expected_justify,
                f"{name}: content placement not aligned as intended")
    for index in range(4, 8):
        require("tile-finance" not in (cards.nth(index).get_attribute("class") or ""),
                "Lower four cards must keep their existing layout")
    positions = cards.evaluate_all("""els => els.slice(0,4).map(el => ({
      cardTop: el.getBoundingClientRect().top,
      headingTop: el.querySelector('.tile-finance-heading').getBoundingClientRect().top
    }))""")
    require(abs(positions[0]["headingTop"]-positions[1]["headingTop"])<1,
            f"First pair title misalignment: {positions}")
    require(abs(positions[2]["headingTop"]-positions[3]["headingTop"])<1,
            f"Second pair title misalignment: {positions}")
    require(page.locator("#tileCommissionSplit").is_visible(),
            "Commission breakdown missing for known sample shift")
    fees = rubles(page.locator("#tileCommissions").inner_text())
    order_line = page.locator("#tileCommissionOrders").inner_text()
    other_line = page.locator("#tileCommissionOther").inner_text()
    require(order_line.startswith("За заказы ") and other_line.startswith("НДС и прочее "),
            "Commission split labels missing")
    order = rubles(order_line.removeprefix("За заказы "))
    other = rubles(other_line.removeprefix("НДС и прочее "))
    require(abs(order + other - fees) < 0.011,
            f"Commission categories do not add to total: {order} + {other} != {fees}")
    require(page.locator("#tileCommissionOrders").evaluate("(x) => x.scrollWidth <= x.clientWidth + 1"),
            "Orders commission text clipped")
    require(page.locator("#tileCommissionOther").evaluate("(x) => x.scrollWidth <= x.clientWidth + 1"),
            "Other commission text clipped")
    totals = page.evaluate("""() => {
      const y=id => document.querySelector(id).getBoundingClientRect().top;
      return {rent:y('#tileRent'),fuel:y('#tileFuel')};
    }""")
    require(abs(totals["fuel"]-totals["rent"]) < 7,
            f"Fuel amount is too far below rent amount: {totals}")
    no_overflow(page, "first four KPI layout")


def test_cash_tile_compact(page):
    """Public demo: gross (yellow) = pre-fee; cash (green) = gross minus fees."""
    for shift in ("s22", "s20", "s21"):
        page.locator(f'#shiftRibbon [data-shift-id="{shift}"]').click()
        page.locator('[data-nav="report"]').click()
        gross = rubles(page.locator("#tileGross").inner_text())
        after = rubles(page.locator("#tileCash").inner_text())
        fees = rubles(page.locator("#tileCommissions").inner_text())
        require(abs(gross - after - fees) < 0.011,
                f"{shift}: gross {gross} minus fees {fees} != cash after fees {after}")
        require("До комиссий" in page.locator('.tile-cash').inner_text(),
                "Human-readable pre-commission label missing")
        require("После комиссий" in page.locator("#tileCashMeta").inner_text(),
                "Post-commission label missing")
        pairs = page.locator(".tile-cash .cash-amount").evaluate_all("""els =>
          els.map(el => ({font: getComputedStyle(el).fontSize,
            x: el.getBoundingClientRect().x, y: el.getBoundingClientRect().y,
            w: el.getBoundingClientRect().width, scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth}))""")
        require(len(pairs) == 2, "Need exactly two cash figures")
        require(pairs[0]["font"] == pairs[1]["font"],
                f"Cash figures must be the same font size: {pairs}")
        require(pairs[0]["y"] < pairs[1]["y"],
                f"Gross and post-commission figures must be stacked: {pairs}")
        require(abs(pairs[0]["x"] - pairs[1]["x"]) < 1,
                f"Cash figures must have matching horizontal alignment: {pairs}")
        require(all(p["scrollWidth"] <= p["clientWidth"]+1 for p in pairs),
                f"Cash figures must not be clipped: {pairs}")
        gross_color = page.locator("#tileGross").evaluate(
            "(el) => getComputedStyle(el).color")
        after_color = page.locator("#tileCash").evaluate(
            "(el) => getComputedStyle(el).color")
        require(gross_color != after_color, "Gross and net colors must differ")
        require(gross_color == "rgb(255, 209, 41)",
                f"Gross color must be taxi-yellow, got {gross_color}")
        require(after_color == "rgb(107, 225, 174)",
                f"Post-commission cash must be green, got {after_color}")
    # Reduce dead space without reducing the cash amount font size.
    heights = page.locator('#report .tile').evaluate_all(
        "(els) => els.map(el => el.getBoundingClientRect().height)")
    require(max(heights) <= 125,
            f"Dashboard tiles are still too tall: {heights}")
    require(min(heights) >= 44, "Touch target too small")
    clipping = page.locator('.tile-cash').evaluate("""el => {
      const bottom=el.getBoundingClientRect().bottom;
      return Array.from(el.querySelectorAll('strong,small,span')).some(child =>
        child.getBoundingClientRect().bottom > bottom + 1);
    }""")
    require(not clipping, "Cash amounts clipped by compact tile")
    no_overflow(page, "compact dashboard tiles")


def test_quick_entry(page):
    """Cash changes both figures immediately; fuel changes net only."""
    page.locator('#shiftRibbon [data-shift-id="s22"]').click()
    require(page.locator("#home").is_visible(), "Quick entry requires home")
    before_cash = rubles(page.locator("#homeCashValue").inner_text())
    before_net = rubles(page.locator("#homeNetValue").inner_text())
    page.locator('[data-quick="cash"]').click()
    require(page.locator("#quickEntryForm").is_visible(), "Cash form didn't open")
    page.locator("#quickAmount").fill("1500")
    page.locator("#quickComment").fill("QA quick cash")
    page.locator(".quick-submit").click()
    require(not page.locator("#quickEntryForm").is_visible(),
            "Quick form must disappear after saving")
    cash = rubles(page.locator("#homeCashValue").inner_text())
    net = rubles(page.locator("#homeNetValue").inner_text())
    require(abs(cash - before_cash - 1500) < 0.011,
            f"Cash didn't rise by full cash fare: {before_cash} -> {cash}")
    require(abs(net - before_net - 1500) < 0.011,
            f"Net didn't rise by cash fare: {before_net} -> {net}")
    page.locator('[data-quick="fuel"]').click()
    require(page.locator("#quickLitresWrap").is_visible(),
            "Fuel entry should offer optional litres")
    page.locator("#quickAmount").fill("399.90")
    page.locator("#quickLitres").fill("6")
    page.locator(".quick-submit").click()
    require(abs(rubles(page.locator("#homeNetValue").inner_text()) - (net - 399.90)) < 0.011,
            "Fuel expense must decrease net profit immediately")
    require(abs(rubles(page.locator("#homeCashValue").inner_text()) - cash) < 0.011,
            "Fuel must not alter after-fee cash")
    page.locator('[data-nav="report"]').click()
    page.locator('#report .tile[data-screen="cash"]').click()
    require(page.locator(".record").filter(has_text="QA quick cash").count() == 1,
            "Quick cash entry missing from detail")
    page.locator("#backHome").click()
    require(page.locator("#report").is_visible(),
            "Back from report details must return to report")
    page.locator('#report .tile[data-screen="fuel"]').click()
    require(page.locator(".record").filter(has_text="6,00 л").count() >= 1,
            "Fuel litres from quick entry missing")
    page.locator("#backHome").click()
    page.locator('[data-nav="home"]').click()


def test_demo_forms(page):
    """Change an invented record, verify its net effect, then remove it."""
    page.locator('#shiftRibbon [data-shift-id="s22"]').click()
    page.locator('[data-nav="report"]').click()
    before = rubles(page.locator("#netNum").inner_text())
    page.locator('#report .tile[data-screen="other"]').click()
    page.locator('[data-add="other"]').click()
    page.locator("#amountInput").fill("27.50")
    page.locator("#commentInput").fill("QA-night-demo-unique")
    page.locator("#entryDateInput").fill("2026-10-23")
    page.locator("#entryTimeInput").fill("01:35")
    page.locator("#saveEntry").click()
    match = page.locator(".record").filter(has_text="QA-night-demo-unique")
    require(match.count() == 1, "Night expense not added")
    match.locator("[data-expand]").click()
    require(
        "Дата: 23.10.2026" in match.inner_text(),
        "Post-midnight record got the wrong calendar date",
    )
    page.locator("#backHome").click()
    after = rubles(page.locator("#netNum").inner_text())
    require(abs((before - after) - 27.50) < 0.01,
            f"Expense did not decrease net by 27.50: {before} -> {after}")
    page.locator('#report .tile[data-screen="other"]').click()
    match = page.locator(".record").filter(has_text="QA-night-demo-unique")
    match.locator("[data-expand]").click()
    page.once("dialog", lambda dialog: dialog.accept())
    match.locator("[data-delete]").click()
    require(
        page.locator(".record").filter(has_text="QA-night-demo-unique").count() == 0,
        "Deleted demo expense still visible",
    )
    page.locator("#backHome").click()
    restored = rubles(page.locator("#netNum").inner_text())
    require(abs(restored - before) < 0.01,
            f"Net not restored after deleting demo expense: {restored}")


def test_settings_easter_egg(page):
    """User-provided turbine image replaces gear with unchanged tappable settings."""
    gear = page.locator("#gear")
    require(gear.is_visible(), "Settings control is not visible")
    require(gear.get_attribute("aria-label") == "Настройки",
            "Settings accessible name was lost")
    image = gear.locator("img.gear-icon-image")
    require(image.count() == 1, "User image did not replace gear")
    require(image.get_attribute("src") == "assets/cogwork-wheel.png",
            "Settings must use the pinned original wiki PNG from this repository")
    # Test the repository asset rather than requesting a third-party image host.
    image.evaluate("(img) => img.decode()")
    require(image.evaluate("(img) => img.complete && img.naturalWidth == 134 && img.naturalHeight == 133"),
            "Settings must display the original 134x133 wiki PNG, not a recreated icon")
    sizes = gear.evaluate("""el => {
      const a=el.getBoundingClientRect(), b=el.querySelector('img').getBoundingClientRect();
      return {width:a.width,height:a.height,iconWidth:b.width,iconHeight:b.height};
    }""")
    require(abs(sizes["width"]-44)<1 and abs(sizes["height"]-44)<1,
            f"Settings tap target changed: {sizes}")
    require(sizes["iconWidth"]<=36 and sizes["iconHeight"]<=36,
            f"Settings icon too large: {sizes}")
    gear.click()
    require(page.locator("#detailTitle").inner_text() == "Ещё",
            "Tapping new icon did not open More menu")
    require(page.locator("#qaDetails").count() == 1,
            "QA settings content missing")
    chips = page.locator(".more-service-chip")
    require(chips.count() == 3, "More must show three compact connection indicators")
    require("демонстрация" in page.locator(".more-service-label").inner_text().lower(),
            "Connection status summary must be explicitly labelled demo")
    # Status dots must be visible next to three service symbols even before opening detail.
    dots = chips.locator(".status-dot")
    require(dots.count() == 3, "Three summary status dots missing")
    for state in ("ok", "error", "warning"):
        require(chips.locator(f".status-dot.{state}").count() == 1,
                f"Summary lacks demonstration state {state}")
    page.locator("#openConnections").click()
    require(page.locator("#detailTitle").inner_text() == "Вход и подключения",
            "Connections menu not opened")
    providers = page.locator(".connect-card")
    require(providers.count() == 3, "Expected three connection providers")
    for key, name, state, auth, sync in (
        ("yandex", "Яндекс Про", "ok", "ok", "ok"),
        ("apark", "Апарк. Водитель", "error", "error", "unknown"),
        ("gmail", "Google · Gmail", "warning", "ok", "warning"),
    ):
        card = page.locator(f'.connect-card[data-provider="{key}"]')
        require(card.count() == 1 and name in card.inner_text(),
                f"Missing connection option: {name}")
        require(card.locator("button.connect-action").is_disabled(),
                f"Authentication for {name} must NOT be active in the demo")
        require(card.locator(f".connect-overall.{state} .status-dot.{state}").count() == 1,
                f"{name}: missing overall state {state}")
        require(card.locator(f".connect-signal.{auth} .status-dot.{auth}").count() >= 1,
                f"{name}: missing authentication state {auth}")
        require(card.locator(f".connect-signal.{sync} .status-dot.{sync}").count() >= 1,
                f"{name}: missing synchronization state {sync}")
    require("ДЕМО" in page.locator(".connect-demo-notice").inner_text(),
            "Fictional statuses are not declared as demo data")
    require(page.locator("input[type=password]").count() == 0,
            "Public mock must not request passwords")
    require(page.locator('input[name*="token"]').count() == 0,
            "Public mock must not request tokens")
    no_overflow(page, "connections")
    page.locator("#backHome").click()
    require(page.locator("#detailTitle").inner_text() == "Ещё",
            "Back from login should return to More")
    page.locator("#backHome").click()


def test_qa_persistence(page):
    """Manual QA must persist per browser and reset only via its own control."""
    page.locator("#gear").click()
    panel = page.locator("#qaDetails")
    require(panel.count() == 1, "QA checklist missing from gear/settings")
    panel.locator("summary").click()
    boxes = panel.locator('input[data-qa-id]')
    require(boxes.count() >= 18, "QA checklist has too few test items")
    require(not boxes.first.is_checked(), "Fresh browser QA unexpectedly checked")
    boxes.first.check()
    require(page.locator("#qaCount").inner_text().startswith("1 /"),
            "QA progress not counted")
    info = page.locator(".qa-device")
    require(info.count() == 1, "Device metadata panel is missing")
    require(info.locator("dd").count() == 6, "Missing OS/browser/screen/date data")
    require("Браузер" in info.inner_text(), "Browser metadata missing")
    require("Система" in info.inner_text(), "OS metadata missing")
    require("Экран" in info.inner_text(), "Screen metadata missing")
    page.locator("#qaModelInput").fill("Синтетический тестовый смартфон")
    # Capture report text without touching the real OS clipboard.
    page.evaluate("""() => {
      window.__qaCaptured = null;
      Object.defineProperty(navigator, 'clipboard', {
        configurable: true,
        value: {writeText: text => {
          window.__qaCaptured = text;
          return Promise.resolve();
        }}
      });
      window.prompt = (_, text) => { window.__qaCaptured = text; return null; };
    }""")
    page.locator("#qaCopy").click()
    page.wait_for_function("window.__qaCaptured !== null")
    report = page.evaluate("window.__qaCaptured")
    for phrase in ("Модель (вручную): Синтетический тестовый смартфон",
                   "Устройство:", "Система:", "Браузер:",
                   "Область браузера:", "Экран:", "Дата проверки:", "[x] "):
        require(phrase in report, f"Copied QA report missing {phrase}")
    require("\\n" not in report,
            "Copied report includes escaped backslash-n instead of newlines")
    no_overflow(page, "QA checklist")

    page.reload(wait_until="domcontentloaded")
    page.locator("#gear").click()
    page.locator("#qaDetails summary").click()
    require(page.locator('input[data-qa-id]').first.is_checked(),
            "QA checklist did not survive browser reload")
    require(page.locator("#qaCount").inner_text().startswith("1 /"),
            "QA progress did not survive reload")
    require(page.locator("#qaModelInput").input_value() == "Синтетический тестовый смартфон",
            "Manually provided device model did not survive reload")

    # Resetting the DEMONSTRATION must not reset the QA checklist.
    page.locator("#resetDemo").click()
    page.locator("#gear").click()
    page.locator("#qaDetails summary").click()
    require(page.locator('input[data-qa-id]').first.is_checked(),
            "Demo reset unexpectedly cleared QA checklist")
    require(page.locator("#qaModelInput").input_value() == "Синтетический тестовый смартфон",
            "Demo reset unexpectedly cleared device model")

    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#qaReset").click()
    require(not page.locator('input[data-qa-id]').first.is_checked(),
            "Explicit QA reset did not clear selected items")
    require(page.locator("#qaCount").inner_text().startswith("0 /"),
            "Reset did not clear QA progress")

    page.reload(wait_until="domcontentloaded")
    page.locator("#gear").click()
    page.locator("#qaDetails summary").click()
    require(not page.locator('input[data-qa-id]').first.is_checked(),
            "QA reset did not persist")
    page.locator("#backHome").click()


def run_case(browser, width, height):
    record = {
        "viewport": f"{width}x{height}",
        "url": SITE,
        "status": "pending",
        "errors": [],
        "unexpected_origins": [],
        "screens": [],
    }
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
    )
    page = context.new_page()
    page.on("pageerror", lambda err: record["errors"].append(str(err)))
    page.on(
        "request",
        lambda request: record["unexpected_origins"].append(request.url)
        if urlparse(request.url).hostname not in (EXPECTED_HOST, None) else None,
    )
    start = time.monotonic()
    try:
        response = page.goto(SITE, wait_until="domcontentloaded", timeout=45000)
        require(response is not None and response.ok,
                f"Page did not load: {response.status if response else 'no response'}")
        page.locator('#homeCashValue').wait_for(timeout=12000)
        require(page.locator('#home .home-kpi').count() == 2,
                "Expected exactly two dashboard KPIs")
        require(page.locator('#report .tile[data-screen]').count() == 8,
                "Report should retain all eight detailed KPI tiles")
        require("вымышлены" in page.locator("#globalNotice").inner_text().lower(),
                "Missing synthetic-data notice")
        no_overflow(page, "home")
        test_one_screen_dashboard(page)
        test_settings_easter_egg(page)
        logo = page.locator("#homeBrand .brand-lockup")
        require(logo.is_visible(), "TaxiCheck wordmark missing")
        require(logo.locator(".brand-taxi").inner_text() == "Taxi", "Taxi wordmark wrong")
        require(logo.locator(".brand-check").inner_text() == "Check", "Check wordmark wrong")
        car = logo.locator(".brand-car")
        require(car.count() == 1, "Yellow taxi icon not present")
        require(car.evaluate("(img) => img.complete && img.naturalWidth > 0"),
                "Yellow taxi icon failed to load/decode")
        require(car.evaluate("(img) => img.getBoundingClientRect().height <= 42"),
                "Taxi icon too large for compact mobile header")
        no_overflow(page, "new TaxiCheck header")
        require(
            page.locator('#shiftRibbon [data-shift-id="s22"]').get_attribute("aria-pressed") == "true",
            "22 October night shift must be selected by default",
        )
        page.screenshot(path=str(OUT / f"pages_{width}_home.jpg"),
                        type="jpeg", quality=72, full_page=True,
                        animations="disabled")
        record["screens"].append("home")

        for shift_id in ("s20", "s21", "s22"):
            assert_shift(page, shift_id, *EXPECTED_SHIFTS[shift_id])
        require(
            page.locator('#shiftRibbon [data-shift-id="s21"] .shift-chip-date-end').inner_text().strip() == "→ 22.10",
            "Previous overnight shift must end on 22 October",
        )
        require(
            page.locator('#shiftRibbon [data-shift-id="s22"] .shift-chip-date-end').inner_text().strip() == "→ 23.10",
            "Selected overnight shift must end on 23 October",
        )

        test_quick_entry(page)
        page.locator('[data-nav="analytics"]').click()
        require(page.locator("#analytics").is_visible(), "Analytics tab is not accessible")
        require(page.locator("#report").is_hidden(), "Report should not overlap analytics")
        require("Графики появятся" in page.locator("#analytics").inner_text(),
                "Analytics should be an honest placeholder, not invented chart data")
        no_overflow(page, "analytics placeholder")
        page.locator('[data-nav="report"]').click()
        require(page.locator("#report").is_visible(), "Report tab didn't open")
        require(page.locator("#netCard").is_visible(), "Hourly metrics missing from report")
        page.screenshot(path=str(OUT / f"pages_{width}_report.jpg"),
                        type="jpeg", quality=72, full_page=True,
                        animations="disabled")
        record["screens"].append("report")
        for screen in ("cash", "commissions", "rent", "fuel",
                       "other", "bonuses", "mileage", "consumption"):
            page.locator(f'#report .tile[data-screen="{screen}"]').click()
            require(page.locator("#detail").is_visible(),
                    f"Details not opened: {screen}")
            no_overflow(page, f"details {screen}")
            page.locator("#backHome").click()
            record["screens"].append(screen)

        test_first_four_finance_tiles(page)
        test_cash_tile_compact(page)
        test_demo_forms(page)
        page.locator('[data-nav="home"]').click()
        test_qa_persistence(page)
        record["screens"].append("qa_checklist")
        require(not record["errors"], f"JavaScript exceptions: {record['errors']}")
        require(not record["unexpected_origins"],
                f"Unexpected external requests: {record['unexpected_origins']}")
        record["status"] = "passed"
    except Exception as exc:
        record["status"] = "failed"
        record["failure"] = f"{type(exc).__name__}: {exc}"
        record["traceback"] = traceback.format_exc(limit=6)
        try:
            page.screenshot(path=str(OUT / f"pages_{width}_failure.jpg"),
                            type="jpeg", quality=72, full_page=True)
        except Exception:
            pass
    finally:
        record["seconds"] = round(time.monotonic() - start, 2)
        context.close()
    return record


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for width, height in VIEWPORTS:
        row = run_case(browser, width, height)
        CASES.append(row)
        print(f"{row['viewport']}: {row['status']}; {row.get('failure', '')}",
              flush=True)
    browser.close()

report = {
    "source": "public GitHub Pages (not local and not Netlify)",
    "url": SITE,
    "passed": sum(x["status"] == "passed" for x in CASES),
    "total": len(CASES),
    "cases": CASES,
}
(OUT / "github_pages_report.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8",
)
print(f"GitHub Pages Playwright: {report['passed']}/{report['total']} passed",
      flush=True)
if report["passed"] != report["total"]:
    raise SystemExit(1)
