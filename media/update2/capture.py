"""Capture real screens of the four BedAlert apps for the update video.

Needs the API in dev mode with fresh demo data and the built apps served
(see frontend/e2e/smoke.py). Walks the same flows as the browser test and
saves crisp screenshots (phone screens at 3x) into <out_dir>.

    python capture.py http://localhost:4173 <out_dir>

Map tiles are replaced by a plain grid, so the capture never depends on the
tile server (blocked in some sandboxes) and shows no third-party map art.
"""
import json
import pathlib
import re
import struct
import sys
import zlib

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1]
OUT = pathlib.Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
KUMASI = {"latitude": 6.69, "longitude": -1.62}
CHROME = next(iter(sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome"))), None)
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3}


def plain_tile() -> bytes:
    """A 256x256 light-grey PNG with a faint grid."""
    rows = []
    for y in range(256):
        row = bytearray([0])
        for x in range(256):
            v = 226 if (x % 64 == 0 or y % 64 == 0) else 234
            row += bytes((v, v + 3, v + 6))
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 256, 256, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


TILE = plain_tile()


def ctx(browser, **kw):
    c = browser.new_context(geolocation=KUMASI, permissions=["geolocation"], **kw)
    c.route(re.compile(r".*basemaps\.cartocdn\.com.*"), lambda r: r.fulfill(status=200, content_type="image/png", body=TILE))
    return c


BOXES = {}


def _rel(el, within):
    b = el.bounding_box()
    o = within.bounding_box() if within is not None else {"x": 0, "y": 0}
    return b, o


def tap(name, button, within=None):
    """Remember where `button` is in screenshot `name` (CSS px), so the video
    can show a tap in the right place. `within`: the element the screenshot
    was taken of; omit for page screenshots."""
    b, o = _rel(button, within)
    BOXES.setdefault(name, {})["tap"] = {"x": b["x"] - o["x"] + b["width"] / 2, "y": b["y"] - o["y"] + b["height"] / 2}


def mark(name, el, within):
    """Remember a box to highlight (or blur) in element screenshot `name`."""
    b, o = _rel(el, within)
    BOXES.setdefault(name, {})["box"] = {"x": b["x"] - o["x"], "y": b["y"] - o["y"], "w": b["width"], "h": b["height"]}


def card_shot(name, el):
    """Screenshot of one element; records its CSS width for the video."""
    el.scroll_into_view_if_needed()
    BOXES.setdefault(name, {})["w"] = el.bounding_box()["width"]
    shot(el, name)


def shot(target, name, **kw):
    target.screenshot(path=str(OUT / f"{name}.png"), **kw)
    print("  ·", name)


def staff(browser, path, email, **kw):
    page = ctx(browser, **kw).new_page()
    page.on("pageerror", lambda e: print("PAGE ERROR:", e))
    page.goto(f"{BASE}{path}")
    page.get_by_label("Work email").fill(email)
    page.get_by_role("button", name="Sign in").click()
    return page


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(CHROME) if CHROME else None)

        print("Family app")
        fam = ctx(browser, **PHONE).new_page()
        fam.goto(BASE + "/")
        expect(fam.get_by_text("Find a free hospital bed near you")).to_be_visible()
        fam.wait_for_timeout(600)
        shot(fam, "f1-home")
        tap("f1-home", fam.locator("button", has_text="Accident, chest pain"))
        fam.locator("button", has_text="Accident, chest pain").click()
        expect(fam.get_by_role("button", name="Hold a bed").first).to_be_visible()
        fam.wait_for_timeout(800)
        shot(fam, "f2-list")
        tap("f2-list", fam.get_by_role("button", name="Hold a bed").first)
        fam.get_by_role("button", name="Hold a bed").first.click()
        fam.get_by_label("Phone number").fill("024 123 4567")
        fam.wait_for_timeout(300)
        shot(fam, "f3-phone")
        tap("f3-phone", fam.get_by_role("button", name="Send me a code"))
        fam.get_by_role("button", name="Send me a code").click()
        code = fam.locator("text=Your code is").locator("b").inner_text()
        fam.locator("input[autocomplete=one-time-code]").fill(code)
        fam.wait_for_timeout(300)
        shot(fam, "f4-otp")
        fam.get_by_role("button", name="Confirm").click()
        fam.get_by_role("button", name="Road accident").click()
        fam.get_by_role("button", name="18-39").click()
        fam.get_by_role("button", name="Male", exact=True).click()
        fam.locator("textarea").fill("Conscious, leg injury")
        fam.wait_for_timeout(300)
        shot(fam, "f5-details")
        tap("f5-details", fam.get_by_role("button", name="Hold this bed"))
        fam.get_by_role("button", name="Hold this bed").click()
        expect(fam.get_by_text("Your bed code")).to_be_visible()
        bed_code = fam.locator(".tracking-\\[0\\.15em\\]").inner_text()
        fam.wait_for_timeout(600)
        shot(fam, "f6-held")

        print("Hospital portal (phone)")
        nurse = staff(browser, "/hospital/", "nurse.kath@bedalert.dev", **PHONE)
        expect(nurse.get_by_role("heading", name="Incoming patients")).to_be_visible()
        card = nurse.locator("div.rounded-2xl", has_text=bed_code).last
        expect(card).to_be_visible()
        card.scroll_into_view_if_needed()
        nurse.wait_for_timeout(400)
        shot(nurse, "h1-incoming")
        card_shot("h1-card", card)
        tap("h1-card", card.get_by_role("button", name="✓ Accept"), within=card)
        card.get_by_role("button", name="✓ Accept").click()
        expect(card.get_by_text("Accepted")).to_be_visible()
        nurse.wait_for_timeout(400)
        card_shot("h2-card-accepted", card)
        expect(fam.get_by_text("✓ Hospital confirmed")).to_be_visible(timeout=15000)
        fam.wait_for_timeout(500)
        shot(fam, "f7-confirmed")

        print("Hospital beds")
        beds = staff(browser, "/hospital/", "nurse.kath@bedalert.dev", **PHONE)
        expect(beds.get_by_role("heading", name="Incoming patients")).to_be_visible()
        section = beds.locator("section").filter(has=beds.get_by_role("button", name="+1 bed freed")).last
        section.scroll_into_view_if_needed()
        beds.wait_for_timeout(400)
        card_shot("h3-beds", section)

        print("Dispatch console")
        disp = staff(browser, "/dispatch/", "dispatch.ashanti@bedalert.dev",
                     viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        expect(disp.get_by_text("New emergency")).to_be_visible()
        disp.get_by_role("button", name="use this device’s location").click()
        disp.get_by_role("button", name="Critical").click()
        disp.locator("select").filter(has_text="Choose…").select_option("road_accident")
        disp.get_by_role("button", name="Find beds").click()
        expect(disp.get_by_text("Best hospitals now")).to_be_visible()
        disp.wait_for_timeout(1200)
        ranked = disp.locator("div.rounded-2xl").filter(has_text="Best hospitals now").last
        card_shot("d1-options", ranked)
        tap("d1-options", disp.get_by_role("button", name="Hold best bed"), within=ranked)
        disp.get_by_role("button", name="Hold best bed").click()
        expect(disp.get_by_text("Send the ambulance to")).to_be_visible()
        amb_code = disp.locator(".font-mono-data.font-bold.text-2xl").inner_text()
        disp.wait_for_timeout(900)
        card_shot("d2-held", disp.locator("div.rounded-2xl").filter(has_text="Send the ambulance to").last)

        print("Decline and re-route")
        nurse.reload()
        amb = nurse.locator("div.rounded-2xl", has_text=amb_code).last
        expect(amb).to_be_visible(timeout=15000)
        amb.scroll_into_view_if_needed()
        amb.get_by_role("button", name="Decline").click()
        amb.get_by_placeholder(re.compile("Reason")).fill("CT scanner down")
        nurse.wait_for_timeout(300)
        card_shot("h4-declining", amb)
        tap("h4-declining", amb.get_by_role("button", name="Confirm decline"), within=amb)
        amb.get_by_role("button", name="Confirm decline").click()
        expect(disp.get_by_text("Re-routed")).to_be_visible(timeout=15000)
        disp.wait_for_timeout(900)
        held = disp.locator("div.rounded-2xl").filter(has_text="Send the ambulance to").last
        card_shot("d3-rerouted", held)
        mark("d3-rerouted", held.get_by_text("Re-routed:"), held)

        print("API key")
        hadmin = staff(browser, "/hospital/", "admin.kath@bedalert.dev",
                       viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        hadmin.get_by_role("button", name="API keys").click()
        hadmin.get_by_placeholder(re.compile("Label")).fill("Hospital records system")
        hadmin.get_by_role("button", name="Create key").click()
        expect(hadmin.get_by_text("Copy this key now")).to_be_visible()
        hadmin.wait_for_timeout(400)
        keycard = hadmin.locator("div.rounded-2xl").filter(has_text="Connect your hospital system").first
        card_shot("a1-apikey", keycard)
        mark("a1-apikey", keycard.locator("code"), keycard)

        print("Network admin")
        admin = staff(browser, "/admin/", "admin@bedalert.dev",
                      viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        expect(admin.get_by_text("Before verifying")).to_be_visible()
        admin.locator("select").first.select_option("verified")
        expect(admin.get_by_text("Komfo Anokye Teaching Hospital (DEMO)")).to_be_visible()
        admin.wait_for_timeout(600)
        card_shot("a2-admin", admin.locator("div.rounded-2xl").filter(has_text="Komfo Anokye Teaching Hospital (DEMO)").last)

        browser.close()
    (OUT / "taps.json").write_text(json.dumps(BOXES, indent=1))
    print("done")


if __name__ == "__main__":
    main()
