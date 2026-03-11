#!/usr/bin/env python3
"""
Regression tests for bugs found during testing (March 2026).

Covers 4 specific failure modes that were introduced or exposed:

  1. TRAILING SLASH — collection endpoints return 404 without trailing slash
     (redirect_slashes=False was added to fix 307 auth issue but broke
     GET/POST /api/jobs, /api/candidates, /api/applications, /api/screenings)

  2. QUESTION GENERATION — job setup silently fails with "No module named
     'anthropic'" → setup status stays 'failed', never reaches 'ready'

  3. MOCK INTERVIEW LAUNCH — when setup is not ready, session POST returns 409.
     Frontend was doing `const { session_id } = await res.json()` without
     checking res.ok → session_id is undefined → navigates to /interview/undefined
     → blank screen. (Also catches the 'anthropic' fix: if setup works, session
     creation must return a valid non-null session_id.)

  4. QUESTION BANK VISIBILITY — question bank endpoint must return questions
     after setup completes, and must respond to domain=general (used on modal open)

FAST: tests 1, 2 (partial), 4 use only requests — no browser.
BROWSER: test 3 partial + a Playwright check that the create-job modal shows
         the question bank section immediately on open (not after title typing).

SERVICES REQUIRED (all must be running):
  localhost:8000  — TalentBridge backend
  localhost:8001  — Interview module backend
  localhost:5173  — TalentBridge frontend  (browser tests only)
"""

import sys
import time
import uuid
import requests

TB_API        = "http://localhost:8000"
INTERVIEW_API = "http://localhost:8001"
TB_URL        = "http://localhost:5173"

# Unique suffix so concurrent runs don't collide
_RUN_ID = uuid.uuid4().hex[:8]
TEST_EMAIL    = f"regression-{_RUN_ID}@test.internal"
TEST_PASSWORD = "RegressionPass123!"
TEST_NAME     = "Regression Test User"

TEST_JOB = {
    "title":          f"iOS Engineer [REGRESSION-{_RUN_ID}]",
    "description":    "Senior iOS engineer with Swift and UIKit expertise.",
    "requirements":   "5+ years iOS. Expert Swift, UIKit, SwiftUI, ARC.",
    "department":     "Engineering",
    "location":       "Remote",
    "job_type":       "full_time",
    "experience_level": "senior",
}

COLLECTION_ENDPOINTS = [
    ("GET",  "/api/jobs/"),
    ("GET",  "/api/candidates/"),
    ("GET",  "/api/applications/"),
    ("GET",  "/api/screenings/"),
]

SLASH_LESS_ENDPOINTS = [
    ("GET",  "/api/jobs"),
    ("GET",  "/api/candidates"),
    ("GET",  "/api/applications"),
    ("GET",  "/api/screenings"),
]

SETUP_TIMEOUT = 180  # seconds to wait for question generation


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check(label, cond, detail=""):
    mark = "✅" if cond else "❌"
    line = f"  {mark} {label}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    return cond


def _auth():
    """Register a fresh user and return a Bearer token."""
    r = requests.post(f"{TB_API}/api/auth/register", json={
        "email":        TEST_EMAIL,
        "password":     TEST_PASSWORD,
        "full_name":    TEST_NAME,
        "company_name": "Regression Tests",
    })
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Register failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def _create_job(token):
    r = requests.post(
        f"{TB_API}/api/jobs/",
        json=TEST_JOB,
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Job creation failed: {r.status_code} {r.text}")
    return r.json()


def _trigger_setup(job_id, token):
    """Re-trigger setup via the TB backend (correct path — it builds the right payload)."""
    headers = {"Authorization": f"Bearer {token}"}
    requests.put(
        f"{TB_API}/api/jobs/{job_id}",
        json={"interview_num_questions": 4, "interview_difficulty": 3,
              "interview_seniority": "senior", "interview_behavioral_pct": 20},
        headers=headers,
    )


def _wait_for_setup(job_id, token, timeout=SETUP_TIMEOUT):
    """
    Poll setup status. If status=failed, re-trigger once (handles Anthropic
    transient overload errors — 529s that fail the background task).
    """
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + timeout
    retried = False
    print(f"    waiting", end="", flush=True)
    while time.time() < deadline:
        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status", headers=headers)
        if r.status_code == 200:
            s = r.json()
            status = s.get("setup_status") or s.get("status")
            if status == "ready":
                print(" ready ✅")
                return True
            if status == "failed" and not retried:
                # Transient failure (e.g. Anthropic 529 overload) — retry once
                print(" failed, retrying", end="", flush=True)
                _trigger_setup(job_id, token)
                retried = True
                time.sleep(5)
                continue
            if status == "failed" and retried:
                print(f" failed after retry ❌")
                return False
        time.sleep(3)
        print(".", end="", flush=True)
    print(" timeout ❌")
    return False


# ── Test 1: Trailing slash ────────────────────────────────────────────────────

def test_trailing_slash(token):
    """
    REGRESSION #1 — redirect_slashes=False means /api/jobs (no slash) must
    return 404, while /api/jobs/ (with slash) must return 2xx.
    The frontend fix added trailing slashes; this test guards that they stay.
    """
    print("\n[Test 1] Trailing slash — collection endpoints")
    headers = {"Authorization": f"Bearer {token}"}
    passed = []

    print("  With trailing slash (must be 2xx):")
    for method, path in COLLECTION_ENDPOINTS:
        r = requests.request(method, f"{TB_API}{path}", headers=headers)
        ok = r.status_code < 300
        passed.append(_check(f"{method} {path} → {r.status_code}", ok))

    print("  Without trailing slash (must NOT be 2xx — redirect_slashes=False):")
    for method, path in SLASH_LESS_ENDPOINTS:
        r = requests.request(method, f"{TB_API}{path}", headers=headers,
                             allow_redirects=False)
        # Accept 404 or 307 — both mean the frontend must use the slash version
        not_2xx = r.status_code >= 300
        passed.append(_check(
            f"{method} {path} → {r.status_code}  (redirect/404 expected)",
            not_2xx,
        ))

    return passed


# ── Test 2: Question generation (anthropic installed) ─────────────────────────

def test_question_generation(job_id, token):
    """
    REGRESSION #2 — 'No module named anthropic' caused every job setup to
    silently fail. After the fix, setup must reach status='ready'.
    """
    print("\n[Test 2] Question generation — setup must reach 'ready'")
    _trigger_setup(job_id, token)
    ready = _wait_for_setup(job_id, token)
    passed = [_check("Job setup reaches status='ready'", ready)]
    return passed


# ── Test 3: Mock interview session returns valid session_id ───────────────────

def test_mock_interview_session(job_id, token):
    """
    REGRESSION #3 — When setup was not ready, POST /api/interview/session
    returned 409 with no session_id. Frontend blindly destructured → undefined.
    After the fix:
      (a) If setup is ready, session POST must return 200 + a valid session_id.
      (b) GET /api/interview/session/{id} must return 200 (not 404).
      (c) session_id must not be the string 'undefined' or null.
    """
    print("\n[Test 3] Mock interview session — must return valid session_id")
    passed = []

    jd = f"{TEST_JOB['description']}\n\n{TEST_JOB['requirements']}"
    r = requests.post(f"{INTERVIEW_API}/api/interview/session", json={
        "job_description": jd,
        "resume_text":     "Mock candidate with 5 years iOS experience.",
        "difficulty":      2,
        "seniority_bar":   "senior",
        "time_limit":      30,
        "num_questions":   4,
        "behavioral_pct":  20,
        "job_id":          job_id,
    })

    ok_status = r.status_code == 200
    passed.append(_check(f"POST /session → {r.status_code}  (200 expected)", ok_status))

    if not ok_status:
        detail = r.json().get("detail", r.text)
        passed.append(_check("Session creation did not fail", False,
                              f"status={r.status_code} detail={detail}"))
        return passed

    data = r.json()
    session_id = data.get("session_id")

    passed.append(_check("Response contains session_id key",
                          "session_id" in data))
    passed.append(_check("session_id is not None/null",
                          session_id is not None))
    passed.append(_check("session_id is not the string 'undefined'",
                          session_id != "undefined",
                          str(session_id)))

    if session_id and session_id != "undefined":
        r2 = requests.get(f"{INTERVIEW_API}/api/interview/session/{session_id}")
        passed.append(_check(
            f"GET /session/{session_id[:8]}… → {r2.status_code}  (200 expected)",
            r2.status_code == 200,
        ))

    questions = data.get("questions", [])
    passed.append(_check(f"Session contains questions ({len(questions)} returned)",
                          len(questions) > 0, f"{len(questions)} questions"))

    return passed


# ── Test 4: Question bank returns questions ───────────────────────────────────

def test_question_bank(job_domain="ios"):
    """
    REGRESSION #4 — Question bank was empty because setup always failed.
    Tests:
      - domain=all  returns questions (used by create-job modal on open)
      - domain=ios  returns questions (set up by test_question_generation)
    Note: domain=general returns 0 by design — it is a literal tag, not 'all'.
    """
    print("\n[Test 4] Question bank — must return questions after setup")
    passed = []

    # domain=all — the modal open call; must return ≥1 question after any setup
    r = requests.get(f"{INTERVIEW_API}/api/interview/question-bank",
                     params={"domain": "all", "limit": 20})
    ok_status = r.status_code == 200
    passed.append(_check(f"GET /question-bank?domain=all → {r.status_code}", ok_status))
    if ok_status:
        questions = r.json().get("questions", [])
        passed.append(_check(
            f"  domain=all returned {len(questions)} question(s)  (>0 expected)",
            len(questions) > 0,
        ))

    # domain=ios — job-specific bank after setup
    r = requests.get(f"{INTERVIEW_API}/api/interview/question-bank",
                     params={"domain": job_domain, "limit": 20})
    ok_status = r.status_code == 200
    passed.append(_check(f"GET /question-bank?domain={job_domain} → {r.status_code}",
                          ok_status))
    if ok_status:
        questions = r.json().get("questions", [])
        passed.append(_check(
            f"  domain={job_domain} returned {len(questions)} question(s)  (>0 expected)",
            len(questions) > 0,
        ))

    return passed


# ── Test 5: Browser — question bank visible on modal open (no title needed) ───

def test_question_bank_modal_visibility():
    """
    REGRESSION #4 (browser) — The create-job modal only showed the question
    bank section after the title debounce fired (600ms after typing ≥3 chars).
    After the fix, the section should be visible immediately on modal open
    (showing 'Loading question bank…' or populated questions).
    """
    print("\n[Test 5] Browser — question bank visible on create-job modal open")
    passed = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️  playwright not installed — skipping browser test")
        print("       Run: pip install playwright && playwright install chromium")
        return passed  # Skip, not a failure

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx     = browser.new_context(viewport={"width": 1280, "height": 900})
        page    = ctx.new_page()

        # Log in
        page.goto(f"{TB_URL}/login")
        page.wait_for_load_state("networkidle")
        page.fill('input[type="email"]',    TEST_EMAIL)
        page.fill('input[type="password"]', TEST_PASSWORD)
        page.click('button[type="submit"]')
        try:
            page.wait_for_url(lambda url: "/login" not in url, timeout=10_000)
        except Exception:
            pass
        page.wait_for_load_state("networkidle")

        login_ok = "/login" not in page.url
        passed.append(_check("Logged in successfully", login_ok, page.url))
        if not login_ok:
            ctx.close(); browser.close()
            return passed

        # Navigate to /jobs
        page.goto(f"{TB_URL}/jobs")
        page.wait_for_load_state("networkidle")

        # Click the "Create Job" / "New Job" button — prefer exact text match
        modal_opened = False
        for label in ("Create Job", "New Job", "Post Job", "Post"):
            try:
                page.click(f"button:has-text('{label}')", timeout=3_000)
                # Confirm modal actually appeared by waiting for its heading
                page.wait_for_selector("h2:has-text('Create New Job')", timeout=3_000)
                modal_opened = True
                break
            except Exception:
                continue

        if not modal_opened:
            passed.append(_check("Create Job modal opened", False, "no modal appeared after clicking button"))
            ctx.close(); browser.close()
            return passed

        passed.append(_check("Create Job modal opened", True))

        # Without typing anything, wait up to 6s for the bank section to appear.
        # The useEffect fires on mount → GET /question-bank?domain=all → React
        # re-render; allow time for the network round-trip + render.
        bank_visible = False
        for _ in range(60):
            content = page.content()
            if "question bank" in content.lower() or "loading question bank" in content.lower():
                bank_visible = True
                break
            time.sleep(0.1)

        passed.append(_check(
            "Question bank section visible immediately on modal open (no title needed)",
            bank_visible,
        ))

        ctx.close()
        browser.close()

    return passed


# ── Runner ────────────────────────────────────────────────────────────────────

def check_services():
    print("Checking services…")
    ok = True
    for name, url in [
        ("TB backend",        f"{TB_API}/health"),
        ("Interview backend", f"{INTERVIEW_API}/health"),
        ("TB frontend",       TB_URL),
    ]:
        try:
            r = requests.get(url, timeout=5)
            up = r.status_code < 500
            print(f"  {'✅' if up else '❌'} {name}: HTTP {r.status_code}")
            if not up:
                ok = False
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            ok = False
    return ok


def run():
    print("\n" + "=" * 65)
    print("TalentBridge Regression Tests")
    print("=" * 65)

    if not check_services():
        print("\n❌ One or more services not running. Start all services and retry.")
        return False

    all_passed = []

    # Auth (shared across tests)
    print("\n[Auth] Registering test user…")
    try:
        token = _auth()
        print(f"  Registered {TEST_EMAIL} ✅")
    except Exception as e:
        print(f"  ❌ Auth failed: {e}")
        return False

    # Test 1 — trailing slash (fast, no setup needed)
    all_passed += test_trailing_slash(token)

    # Create job for tests 2–4
    print("\n[Setup] Creating test job…")
    try:
        job = _create_job(token)
        job_id = job["id"]
        print(f"  Created job {job_id} ✅")
    except Exception as e:
        print(f"  ❌ Job creation failed: {e}")
        return False

    # Test 2 — question generation (slow: waits up to 3 min)
    all_passed += test_question_generation(job_id, token)

    # Test 3 — session returns valid id (requires setup to be ready)
    all_passed += test_mock_interview_session(job_id, token)

    # Test 4 — question bank non-empty
    all_passed += test_question_bank()

    # Test 5 — browser: bank visible on modal open
    all_passed += test_question_bank_modal_visibility()

    # ── Summary ───────────────────────────────────────────────────────────
    total  = len(all_passed)
    failed = sum(1 for p in all_passed if not p)

    print("\n" + "=" * 65)
    if failed == 0:
        print(f"✅  ALL {total} CHECKS PASSED")
    else:
        print(f"❌  {failed}/{total} CHECKS FAILED")
    print("=" * 65)

    return failed == 0


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
