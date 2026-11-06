"""End-to-end smoke test across all four BedAlert apps, in a real browser.

Needs the API running in dev mode with demo data (scripts/seed_dev) and the
built apps served (npm run build && npx vite preview --port 4173):

    python e2e/smoke.py [http://localhost:4173] [screenshot_dir]

Walks the real flows: a family holds an ER bed from a phone; a nurse accepts
it and the family sees the confirmation; a dispatcher holds a bed for an
ambulance; the hospital declines and BedAlert re-routes the ambulance;
hospital admin creates an API key; network admin lists hospitals.
"""
import pathlib
import re
import sys

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:4173"
SHOTS = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "e2e-screenshots")
SHOTS.mkdir(parents=True, exist_ok=True)
KUMASI = {"latitude": 6.69, "longitude": -1.62}
# Use the preinstalled Chromium if there is one (CI / cloud containers).
CHROME = next(iter(sorted(pathlib.Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome"))), None)


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"), full_page=True)
    print("  ·", name)


def staff_login(browser, path, email, viewport=None):
    ctx = browser.new_context(viewport=viewport or {"width": 1440, "height": 950}, geolocation=KUMASI, permissions=["geolocation"])
    page = ctx.new_page()
    page.on("pageerror", lambda e: print("PAGE ERROR:", e))
    page.goto(f"{BASE}{path}")
    page.get_by_label("Work email").fill(email)
    page.get_by_role("button", name="Sign in").click()
    return page


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=str(CHROME) if CHROME else None)

        print("1. Family holds an emergency bed on a phone")
        fam_ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, geolocation=KUMASI, permissions=["geolocation"])
        fam = fam_ctx.new_page()
        fam.on("pageerror", lambda e: print("PAGE ERROR:", e))
        fam.goto(BASE + "/")
        expect(fam.get_by_text("Find a free hospital bed near you")).to_be_visible()
        shot(fam, "01-family-home")
        fam.locator("button", has_text="Accident, chest pain").click()
        expect(fam.get_by_text("Using your location")).to_be_visible()
        expect(fam.get_by_role("button", name="Hold a bed").first).to_be_visible()
        shot(fam, "02-family-list")
        first_name = fam.locator("main .font-display.font-bold.text-lg").first.inner_text()
        fam.get_by_role("button", name="Hold a bed").first.click()
        fam.get_by_label("Phone number").fill("024 123 4567")
        fam.get_by_role("button", name="Send me a code").click()
        code = fam.locator("text=Your code is").locator("b").inner_text()
        fam.locator("input[autocomplete=one-time-code]").fill(code)
        shot(fam, "03-family-otp")
        fam.get_by_role("button", name="Confirm").click()
        fam.get_by_role("button", name="Road accident").click()
        fam.get_by_role("button", name="18-39").click()
        fam.get_by_role("button", name="Male", exact=True).click()
        fam.locator("textarea").fill("Conscious, leg injury")
        shot(fam, "04-family-details")
        fam.get_by_role("button", name="Hold this bed").click()
        expect(fam.get_by_text("Your bed code")).to_be_visible()
        bed_code = fam.locator(".tracking-\\[0\\.15em\\]").inner_text()
        print(f"  held at {first_name}: code {bed_code}")
        shot(fam, "05-family-held")

        print("2. Nurse accepts; the family sees it")
        nurse = staff_login(browser, "/hospital/", "nurse.kath@bedalert.dev")
        expect(nurse.get_by_role("heading", name="Incoming patients")).to_be_visible()
        card = nurse.locator("div.rounded-2xl", has_text=bed_code).last
        expect(card).to_be_visible()
        shot(nurse, "06-hospital-incoming")
        card.get_by_role("button", name="✓ Accept").click()
        expect(card.get_by_text("Accepted")).to_be_visible()
        expect(fam.get_by_text("✓ Hospital confirmed")).to_be_visible(timeout=15000)
        shot(fam, "07-family-confirmed")
        nurse.get_by_role("button", name="+1 bed freed").first.click()
        nurse.wait_for_timeout(800)
        shot(nurse, "08-hospital-accepted")

        print("3. Dispatcher holds a bed for an ambulance")
        disp = staff_login(browser, "/dispatch/", "dispatch.ashanti@bedalert.dev")
        expect(disp.get_by_text("New emergency")).to_be_visible()
        disp.get_by_role("button", name="use this device’s location").click()
        disp.get_by_role("button", name="Critical").click()
        disp.locator("select").filter(has_text="Choose…").select_option("road_accident")
        disp.get_by_role("button", name="Find beds").click()
        expect(disp.get_by_text("Best hospitals now")).to_be_visible()
        disp.wait_for_timeout(1200)
        shot(disp, "09-dispatch-options")
        disp.get_by_role("button", name="Hold best bed").click()
        expect(disp.get_by_text("Send the ambulance to")).to_be_visible()
        amb_code = disp.locator(".font-mono-data.font-bold.text-2xl").inner_text()
        first_hospital = disp.locator(".font-display.font-bold.text-2xl").inner_text()
        print(f"  ambulance hold {amb_code} at {first_hospital}")
        disp.wait_for_timeout(800)
        shot(disp, "10-dispatch-held")

        print("4. Hospital declines; BedAlert re-routes the ambulance")
        nurse.reload()
        amb_card = nurse.locator("div.rounded-2xl", has_text=amb_code).last
        expect(amb_card).to_be_visible(timeout=15000)
        amb_card.get_by_role("button", name="Decline").click()
        amb_card.get_by_placeholder(re.compile("Reason")).fill("CT scanner down")
        shot(nurse, "11-hospital-declining")
        amb_card.get_by_role("button", name="Confirm decline").click()
        expect(disp.get_by_text("Re-routed")).to_be_visible(timeout=15000)
        new_hospital = disp.locator(".font-display.font-bold.text-2xl").inner_text()
        assert new_hospital != first_hospital, (new_hospital, first_hospital)
        print(f"  re-routed to {new_hospital}")
        disp.wait_for_timeout(800)
        shot(disp, "12-dispatch-rerouted")

        print("5. Hospital admin creates an API key")
        hadmin = staff_login(browser, "/hospital/", "admin.kath@bedalert.dev")
        hadmin.get_by_role("button", name="API keys").click()
        hadmin.get_by_placeholder(re.compile("Label")).fill("Hospital system (test)")
        hadmin.get_by_role("button", name="Create key").click()
        expect(hadmin.get_by_text("Copy this key now")).to_be_visible()
        expect(hadmin.locator("code")).to_contain_text("ba_live_")
        shot(hadmin, "13-hospital-api-key")

        print("6. Network admin")
        admin = staff_login(browser, "/admin/", "admin@bedalert.dev")
        expect(admin.get_by_text("Before verifying")).to_be_visible()
        admin.locator("select").first.select_option("verified")
        expect(admin.get_by_text("Komfo Anokye Teaching Hospital (DEMO)")).to_be_visible()
        shot(admin, "14-admin-hospitals")

        print("7. A dispatcher can't open the admin page")
        d2 = staff_login(browser, "/admin/", "dispatch.ashanti@bedalert.dev")
        expect(d2.get_by_text("for the BedAlert team only")).to_be_visible()

        browser.close()
    print("All flows passed.")


if __name__ == "__main__":
    main()
