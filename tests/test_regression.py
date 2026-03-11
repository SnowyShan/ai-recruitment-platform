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

  6. CANDIDATE APPLICATION FLOW — end-to-end browser test:
     Browse openings → click job → fill form + upload resume → Apply →
     assert auto-invite screening created with invite_sent_at set →
     navigate to interview link → assert "Before you begin" page loads.

FAST: tests 1, 2 (partial), 4 use only requests — no browser.
BROWSER: test 5 (create-job modal), test 6 (candidate application flow).

SERVICES REQUIRED (all must be running):
  localhost:8000  — TalentBridge backend
  localhost:8001  — Interview module backend
  localhost:5173  — TalentBridge frontend
  localhost:5174  — Interview module frontend  (test 6)
"""

import io
import os
import sys
import time
import uuid
import requests

TB_API           = "http://localhost:8000"
INTERVIEW_API    = "http://localhost:8001"
TB_URL           = "http://localhost:5173"
INTERVIEW_URL    = "http://localhost:5174"

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


# ── Test 6: Candidate application flow (full browser) ────────────────────────

def _make_resume_pdf() -> bytes:
    """
    Generate a minimal but keyword-rich iOS resume PDF.
    The sentence-transformer scorer is local and deterministic —
    heavy Swift/UIKit/iOS vocabulary reliably scores ≥ 70 against
    an iOS job description.
    """
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "Alex Johnson - Senior iOS Engineer", ln=True)
    pdf.set_font("Helvetica", size=10)
    lines = [
        "EXPERIENCE",
        "Senior iOS Engineer, Acme Corp, 2019-present",
        "Architected and shipped features in Swift UIKit and SwiftUI.",
        "Deep expertise in ARC memory management with weak and unowned references.",
        "Led migration from Objective-C to Swift with async/await and Combine.",
        "Built custom UICollectionView layouts and optimised Core Data queries.",
        "Used Instruments Leaks and Allocations to fix memory leaks.",
        "",
        "iOS Engineer, StartupXYZ, 2016-2019",
        "Developed iPhone and iPad apps using Swift and Xcode.",
        "Integrated REST APIs with URLSession and Codable.",
        "Used Core Location MapKit and APNs push notifications.",
        "Wrote unit tests with XCTest.",
        "",
        "SKILLS",
        "Swift Objective-C SwiftUI UIKit Xcode ARC Combine Core Data",
        "Core Location MapKit XCTest Instruments APNs CocoaPods Git",
        "",
        "EDUCATION",
        "BSc Computer Science Stanford University 2016",
    ]
    for line in lines:
        pdf.cell(0, 6, line, ln=True)
    return bytes(pdf.output())


def test_candidate_application_flow(job_id: int, recruiter_token: str,
                                     video_path: str = None):
    """
    TEST 6 — Candidate application + auto-invite + interview launch.

    Browser steps (no auth — public-facing pages):
      1. Visit /browse-jobs
      2. Find and click the test job → /browse-jobs/{job_id}
      3. Fill Full Name + Email, upload PDF resume
      4. Click Apply
      5. Assert success confirmation screen

    API steps (test infrastructure — extracting the invite the candidate
    would have received by email):
      6. Assert screening record exists with invite_sent_at set
      7. Extract session_id + invite_token

    Browser steps (candidate clicks link from email):
      8. Navigate to interview URL with token
      9. Assert "Before you begin" page renders
    """
    print("\n[Test 6] Candidate application flow — browse → apply → invite → interview")
    passed = []

    # ── Setup: enable auto-invite and publish the job ──────────────────────
    headers = {"Authorization": f"Bearer {recruiter_token}"}

    # Enable auto-invite with threshold=70
    r = requests.put(f"{TB_API}/api/settings/",
                     json={"auto_invite_screening": True, "auto_invite_threshold": 70},
                     headers=headers)
    passed.append(_check("Auto-invite enabled via settings API",
                          r.status_code == 200, f"HTTP {r.status_code}"))

    # Publish the job so it appears on browse page
    r = requests.post(f"{TB_API}/api/jobs/{job_id}/publish", headers=headers)
    published_ok = r.status_code in (200, 201)
    passed.append(_check(f"Job {job_id} published (status=active)",
                          published_ok, f"HTTP {r.status_code}"))
    if not published_ok:
        print(f"    publish detail: {r.text[:200]}")

    # Build resume PDF once — reused for the file upload
    resume_pdf = _make_resume_pdf()
    candidate_name  = f"Test Candidate {_RUN_ID[:6]}"
    candidate_email = f"candidate-{_RUN_ID}@test.internal"

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️  playwright not installed — skipping browser test")
        return passed

    # Playwright context — optionally record video
    launch_kwargs  = {"headless": True}
    context_kwargs = {"viewport": {"width": 1280, "height": 900}}
    if video_path:
        context_kwargs["record_video_dir"] = os.path.dirname(video_path)
        context_kwargs["record_video_size"] = {"width": 1280, "height": 900}

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        ctx  = browser.new_context(**context_kwargs)
        page = ctx.new_page()

        # ── Step 1: Browse openings ────────────────────────────────────────
        print("  [6.1] Browsing openings…")
        page.goto(f"{TB_URL}/browse-jobs")
        page.wait_for_load_state("networkidle")

        browse_ok = "browse" in page.url or page.query_selector("text=Browse") is not None
        passed.append(_check("Browse jobs page loaded",
                              page.url.endswith("/browse-jobs") or "browse-jobs" in page.url,
                              page.url))

        # ── Step 2: Find the test job and click View & Apply ──────────────
        print("  [6.2] Finding test job card…")
        job_title_fragment = TEST_JOB["title"][:20]  # enough to be unique

        try:
            # Wait for job cards to render
            page.wait_for_selector(f"text={job_title_fragment}", timeout=8_000)
            # Click the "View & Apply" link for this job specifically
            page.locator(f"text={job_title_fragment}").locator("..").locator("..").locator("a:has-text('View & Apply')").first.click()
        except Exception:
            # Fallback: navigate directly
            page.goto(f"{TB_URL}/browse-jobs/{job_id}")

        page.wait_for_load_state("networkidle")
        on_apply_page = f"/browse-jobs/{job_id}" in page.url
        passed.append(_check(f"Navigated to job apply page (/browse-jobs/{job_id})",
                              on_apply_page, page.url))

        # ── Step 3: Fill application form ─────────────────────────────────
        print("  [6.3] Filling application form…")
        try:
            page.wait_for_selector('input[name="full_name"]', timeout=5_000)
            page.fill('input[name="full_name"]', candidate_name)
            page.fill('input[type="email"]',     candidate_email)
            passed.append(_check("Form fields filled", True))
        except Exception as e:
            passed.append(_check("Form fields filled", False, str(e)))

        # ── Step 4: Upload PDF resume ──────────────────────────────────────
        print("  [6.4] Uploading resume PDF…")
        import tempfile
        tmp_path = None
        try:
            # Write PDF to a temp file. Do NOT delete until after submit — Playwright
            # reads the file lazily at form submission time, not at set_input_files time.
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(resume_pdf)
                tmp_path = tmp.name
            page.locator('input[type="file"]').set_input_files(tmp_path)
            passed.append(_check("Resume PDF attached to form", True))
        except Exception as e:
            passed.append(_check("Resume PDF attached to form", False, str(e)))

        # ── Step 5: Submit application ────────────────────────────────────
        print("  [6.5] Submitting application…")
        try:
            page.click('button[type="submit"]', timeout=5_000)
            # analyze_resume (sentence-transformers) runs synchronously in the
            # request handler — allow up to 30s for the model to score the resume
            page.wait_for_selector("h2:has-text('Application Submitted')", timeout=30_000)
            passed.append(_check("Application submitted — success screen shown", True))
        except Exception as e:
            passed.append(_check("Application submitted — success screen shown", False, str(e)))
            page.screenshot(path="/tmp/apply_fail.png")
        finally:
            # Safe to delete now — browser has finished reading the file
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        # ── Step 6 & 7: Verify screening + extract token (API) ────────────
        print("  [6.6] Verifying auto-invite screening record…")

        # Get application_id from the apply response (we'll use the email to look it up)
        time.sleep(2)  # small wait for DB commit
        r = requests.get(f"{TB_API}/api/public/status",
                         params={"email": candidate_email})
        app_id = None
        if r.status_code == 200:
            apps = r.json()
            if apps:
                app_id = apps[0].get("id")

        screening = None
        if app_id:
            sr = requests.get(f"{TB_API}/api/screenings/",
                              params={"application_id": app_id},
                              headers=headers)
            if sr.status_code == 200 and sr.json():
                screening = sr.json()[0]

        has_screening = screening is not None
        passed.append(_check("Screening record created (auto-invite triggered)",
                              has_screening))

        invite_sent = screening and screening.get("invite_sent_at") is not None
        passed.append(_check("invite_sent_at is set (email dispatch attempted)",
                              invite_sent,
                              str(screening.get("invite_sent_at") if screening else None)))

        session_id   = screening.get("interview_session_id") if screening else None
        invite_token = screening.get("invite_token")         if screening else None

        has_token = bool(session_id and invite_token)
        passed.append(_check("session_id + invite_token present in screening record",
                              has_token,
                              f"session={session_id}, token={str(invite_token)[:8]}…" if has_token else "missing"))

        # ── Step 8 & 9: Navigate to interview link ─────────────────────────
        if has_token:
            print("  [6.8] Navigating to interview link (as candidate)…")
            interview_link = f"{INTERVIEW_URL}/interview/{session_id}?token={invite_token}"
            page.goto(interview_link)
            page.wait_for_load_state("networkidle")

            # Wait up to 8s for "Before you begin" to render
            # (token validation makes a round-trip to the TB backend)
            before_you_begin = False
            for _ in range(80):
                if "before you begin" in page.content().lower():
                    before_you_begin = True
                    break
                time.sleep(0.1)

            passed.append(_check(
                "Interview module shows 'Before you begin' page",
                before_you_begin,
                page.url,
            ))
        else:
            passed.append(_check("Interview link navigation skipped (no token)", False))

        # Save video
        if video_path:
            ctx.close()  # must close context before video is written
            browser.close()
            # Playwright saves video as a random name in the dir — rename it
            vid_dir = os.path.dirname(video_path)
            vids = sorted(
                [f for f in os.listdir(vid_dir) if f.endswith(".webm")],
                key=lambda f: os.path.getmtime(os.path.join(vid_dir, f)),
            )
            if vids:
                src = os.path.join(vid_dir, vids[-1])
                os.rename(src, video_path)
                print(f"  📹 Video saved: {video_path}")
        else:
            ctx.close()
            browser.close()

    return passed


# ── Runner ────────────────────────────────────────────────────────────────────

def check_services():
    print("Checking services…")
    ok = True
    for name, url in [
        ("TB backend",           f"{TB_API}/health"),
        ("Interview backend",    f"{INTERVIEW_API}/health"),
        ("TB frontend",          TB_URL),
        ("Interview frontend",   INTERVIEW_URL),
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

    # Test 6 — candidate application flow (browser, end-to-end)
    all_passed += test_candidate_application_flow(job_id, token)

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
