#!/usr/bin/env python3
"""
E2E navigation test — Login → Dashboard → Jobs tab.

Verifies the fix for the bug where clicking sidebar links after login would
either fail to navigate or silently log the user out.

Flow:
  1. Open browser and navigate to the app
  2. Log in with test credentials
  3. Assert: landed on /dashboard with dashboard content visible
  4. Click the "Jobs" sidebar link
  5. Assert: navigated to /jobs with jobs content visible (not logged out)

REQUIREMENTS:
  pip install playwright && playwright install chromium

SERVICES MUST BE RUNNING:
  localhost:8000  — TalentBridge backend
  localhost:5173  — TalentBridge frontend
"""

import sys
import time
import requests

TB_API  = "http://localhost:8000"
TB_URL  = "http://localhost:5173"

TEST_EMAIL    = "test3@test.com"
TEST_PASSWORD = "testpassword"


def check_services():
    print("Checking services…")
    for name, url in [("TB backend", f"{TB_API}/health"),
                      ("TB frontend", TB_URL)]:
        try:
            r = requests.get(url, timeout=5)
            up = r.status_code < 500
            print(f"  {'✅' if up else '❌'} {name}: HTTP {r.status_code}")
            if not up:
                return False
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            return False
    return True


def run_test():
    print("\n" + "=" * 60)
    print("TalentBridge E2E Navigation Test — Login → Dashboard → Jobs")
    print("=" * 60 + "\n")

    if not check_services():
        print("\n❌ Services not ready. Start all services and retry.")
        return False

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ playwright not installed. Run: pip install playwright && playwright install chromium")
        return False

    passed = []

    def check(desc, cond, detail=""):
        mark = "✅" if cond else "❌"
        print(f"  {mark} {desc}" + (f"  [{detail}]" if detail else ""))
        passed.append(cond)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # ── Step 1: Load login page ────────────────────────────────────────
        print("[Step 1] Load login page")
        page.goto(f"{TB_URL}/login")
        page.wait_for_load_state("networkidle")

        check("Login page loaded",
              "login" in page.url or page.title() != "",
              page.url)

        # ── Step 2: Log in ─────────────────────────────────────────────────
        print("\n[Step 2] Log in as", TEST_EMAIL)
        page.fill('input[type="email"]', TEST_EMAIL)
        page.fill('input[type="password"]', TEST_PASSWORD)
        page.click('button[type="submit"]')

        # Wait for React Router to navigate away from /login (client-side routing)
        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=10_000)
        except Exception:
            pass  # URL check below will catch the failure
        page.wait_for_load_state("networkidle")

        print(f"  URL after login: {page.url}")

        check("Redirected away from login",
              "/login" not in page.url,
              page.url)

        check("Landed on dashboard",
              "/dashboard" in page.url,
              page.url)

        # ── Step 3: Assert dashboard content is visible ────────────────────
        print("\n[Step 3] Assert dashboard content")
        try:
            page.wait_for_selector("text=Dashboard", timeout=5_000)
            dashboard_visible = True
        except Exception:
            dashboard_visible = False

        check("Dashboard heading visible", dashboard_visible)

        # Confirm we're not on the login screen
        login_form_visible = page.query_selector('input[type="password"]') is not None
        check("Login form is NOT visible (not logged out)", not login_form_visible)

        # ── Step 4: Click the Jobs sidebar link ───────────────────────────
        print("\n[Step 4] Click Jobs tab in sidebar")
        try:
            jobs_link = page.wait_for_selector("nav a[href='/jobs']", timeout=5_000)
            jobs_link.click()
        except Exception:
            # Fallback: try text match
            try:
                page.click("text=Jobs", timeout=5_000)
            except Exception as e:
                print(f"  ⚠️  Could not find Jobs link: {e}")

        # Wait for navigation
        for _ in range(20):
            if "/jobs" in page.url:
                break
            time.sleep(0.3)
        page.wait_for_load_state("networkidle")

        print(f"  URL after clicking Jobs: {page.url}")

        # ── Step 5: Assert Jobs page loaded (not logged out) ───────────────
        print("\n[Step 5] Assert Jobs page content")

        check("Navigated to /jobs",
              "/jobs" in page.url,
              page.url)

        check("Not redirected to login",
              "/login" not in page.url,
              page.url)

        try:
            page.wait_for_selector("text=Jobs", timeout=5_000)
            jobs_heading = True
        except Exception:
            jobs_heading = False

        check("Jobs page content visible", jobs_heading)

        # Final check: Log out button visible in sidebar (confirms authenticated layout)
        try:
            logout_visible = page.query_selector("button:has-text('Log out')") is not None
        except Exception:
            logout_visible = False
        check("Still authenticated (Log out button present)", logout_visible)

        context.close()
        browser.close()

    print(f"\n{'=' * 60}")
    all_passed = all(passed)
    if all_passed:
        print("✅  ALL CHECKS PASSED")
    else:
        n = sum(1 for p in passed if not p)
        print(f"❌  {n} CHECK(S) FAILED")

    return all_passed


if __name__ == "__main__":
    ok = run_test()
    sys.exit(0 if ok else 1)
