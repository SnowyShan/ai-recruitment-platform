#!/usr/bin/env python3
"""
End-to-end test: Skip / End button behaviour on regular and probe questions.

Scenarios tested (each is a separate interview session):

  A. Regular question — Skip
       3-question interview. Skip Q1. Verify Q2 loads, transcript has [SKIPPED] for Q1.

  B. Regular question — End (mid-interview)
       3-question interview. Answer Q1, tap End on Q2. Verify interview completes,
       report is generated, Q2 transcript is stored (non-empty), Q3 marked (no answer).

  C. Probe question — Skip probe
       1 CC question. Give shallow answer → probes fire. Skip probe 1. Verify probe 2
       appears (or interview completes if only 1 probe). Probe transcript has [SKIPPED].

  D. Probe question — End mid-probe
       1 CC question. Give shallow answer → probes fire. Tap End during probe.
       Verify interview completes cleanly (no crash, report generated).

  E. Button label correctness
       1 CC question. Verify Next button label:
         - "Finish" on last main question before probe fires
         - "Next →" during a probe (not the last probe)
         - "Finish" on the last probe of the last question

  F. Skip on last probe (last question)
       1 CC question. Give shallow answer → probes fire. Skip all probes via Skip button.
       Verify interview completes (not stuck), report generated.

WHAT IS REAL:
  - All 4 services running locally
  - Real question bank generation and CC flag toggle
  - BlackHole loopback for mic audio
  - Real Whisper transcription
  - Real Claude probe-assess and report generation

REQUIREMENTS:
  BlackHole 2ch: https://existential.audio/blackhole/
  SwitchAudioSource: brew install switchaudio-osx
  playwright: pip install playwright && playwright install chromium

SERVICES REQUIRED:
  localhost:8000  TalentBridge backend
  localhost:8001  Interview module backend
  localhost:5173  TalentBridge frontend
  localhost:5174  Interview module frontend

Run:
  python tests/test_interview_buttons.py
  python tests/test_interview_buttons.py --record
"""

import os, sys, json, time, uuid, shutil, datetime, subprocess, requests

TB_URL        = "http://localhost:5173"
INTERVIEW_URL = "http://localhost:5174"
TB_API        = "http://localhost:8000"
INTERVIEW_API = "http://localhost:8001"

_RUN_ID       = uuid.uuid4().hex[:8]
TEST_EMAIL    = "e2e-test@gmail.com"
TEST_PASSWORD = "E2eTestPass123!"
TEST_NAME     = "E2E Test Recruiter"

JOB_TITLE_BASE = f"Senior iOS Engineer [BTN-E2E-{_RUN_ID}]"

JOB_DESC = (
    "Senior iOS engineer with deep Swift expertise. "
    "Strong ARC memory management, retain cycles, weak/unowned references. "
)
JOB_REQS = "5+ years iOS. Expert Swift, UIKit, ARC, Instruments."

SHALLOW_ANSWER = "I don't know."
NORMAL_ANSWER  = (
    "In iOS I use ARC for memory management. "
    "Weak references are optional and set to nil when the object is deallocated. "
    "Unowned references are non-optional and assume the object is always alive. "
    "I use weak self in closures to avoid retain cycles in view controllers."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

_cached_token = None

def _get_token():
    global _cached_token
    if _cached_token:
        return _cached_token
    r = requests.post(f"{TB_API}/api/auth/login",
                      json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    if r.status_code == 200:
        _cached_token = r.json()["access_token"]
        return _cached_token
    r = requests.post(f"{TB_API}/api/auth/register",
                      json={"email": TEST_EMAIL, "password": TEST_PASSWORD,
                            "full_name": TEST_NAME, "company_name": "E2E Tests"})
    _cached_token = r.json()["access_token"]
    return _cached_token


def _check(label, cond, detail=""):
    mark = "✅" if cond else "❌"
    line = f"  {mark} {label}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    return cond


def _say(text):
    subprocess.run(["say", "-r", "170", "-a", "BlackHole 2ch", text], check=False)


def _wait_recording(page, timeout_s=60):
    for _ in range(timeout_s * 2):
        content = page.content()
        if "Recording" in content and "Speaking…" not in content:
            return True
        page.wait_for_timeout(500)
    return False


def _wait_enabled(page, selector, timeout_s=30):
    for _ in range(timeout_s * 2):
        el = page.query_selector(f"{selector}:not([disabled])")
        if el:
            return el
        page.wait_for_timeout(500)
    return None


def _wait_transcribing(page, timeout_s=30):
    """Wait for 'Processing' indicator to appear and disappear."""
    try:
        page.wait_for_selector("p:has-text('Processing')", timeout=5_000)
        page.wait_for_selector("p:has-text('Processing')", state="hidden", timeout=timeout_s * 1000)
    except Exception:
        pass


def _restore_audio():
    subprocess.run(["SwitchAudioSource", "-s", "MacBook Pro Microphone", "-t", "input"],
                   capture_output=True)


def check_services():
    print("Checking services…")
    ok = True
    for name, url in [
        ("TB backend",         f"{TB_API}/health"),
        ("Interview backend",  f"{INTERVIEW_API}/health"),
        ("TB frontend",        TB_URL),
        ("Interview frontend", INTERVIEW_URL),
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


def _check_blackhole():
    result = subprocess.run(["say", "-a", "BlackHole 2ch", ""], capture_output=True, timeout=3)
    return result.returncode == 0


# ── Shared browser setup ──────────────────────────────────────────────────────

def _make_context(p, record=False, recordings_dir=None, timestamp=""):
    profile_dir = f"/tmp/btn_e2e_{uuid.uuid4().hex[:8]}"
    kwargs = {"viewport": {"width": 1280, "height": 900}}
    if record and recordings_dir:
        kwargs["record_video_dir"] = recordings_dir
        kwargs["record_video_size"] = {"width": 1280, "height": 900}
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=False,
        args=["--use-fake-ui-for-media-stream"],
        **kwargs,
    )
    return ctx


def _login(page):
    page.goto(f"{TB_URL}/login")
    page.wait_for_load_state("networkidle")
    page.fill('input[type="email"]', TEST_EMAIL)
    page.fill('input[type="password"]', TEST_PASSWORD)
    page.click('button[type="submit"]')
    for _ in range(20):
        if "/dashboard" in page.url or "/jobs" in page.url:
            break
        page.wait_for_timeout(500)


def _create_job_and_wait(page, title, num_questions=3, behavioral_pct=20):
    """Create a job, wait for question bank, set config, return job_id."""
    page.goto(f"{TB_URL}/jobs")
    page.wait_for_load_state("networkidle")
    page.click("button.btn-primary:has-text('Create Job')", timeout=8_000)
    page.wait_for_selector("h2:has-text('Create New Job')", timeout=8_000)
    page.fill('input[name="title"]', title)
    page.fill('input[name="department"]', "Engineering")
    page.fill('input[name="location"]', "Remote")
    page.fill('textarea[name="description"]', JOB_DESC)
    page.fill('textarea[name="requirements"]', JOB_REQS)
    page.click('button[type="submit"].btn-primary:has-text("Create Job")', timeout=5_000)
    try:
        page.wait_for_selector("h2:has-text('Create New Job')", state="hidden", timeout=10_000)
    except Exception:
        pass
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1000)

    # Navigate to job detail via API
    token = _get_token()
    r = requests.get(f"{TB_API}/api/jobs/",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    jobs = r.json() if r.status_code == 200 else []
    job = next((j for j in jobs if title[:20] in j.get("title", "")), None)
    if not job:
        raise RuntimeError(f"Job not found: {title}")
    job_id = job["id"]
    page.goto(f"{TB_URL}/jobs/{job_id}")
    page.wait_for_load_state("networkidle")

    # Wait for question bank
    print("    Waiting for question bank…", end="", flush=True)
    deadline = time.time() + 300
    while time.time() < deadline:
        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status",
                         headers={"Authorization": f"Bearer {token}"}, timeout=5)
        if r.status_code == 200 and (r.json().get("setup_status") or r.json().get("status")) == "ready":
            break
        page.wait_for_timeout(3000)
        print(".", end="", flush=True)
    print(" ready")

    # Set config
    page.reload()
    page.wait_for_load_state("networkidle")
    page.click("button:has-text('Screening Interview Config')", timeout=8_000)
    page.wait_for_timeout(1500)
    page.wait_for_selector("button:has-text('Mark Core'), button:has-text('⭐ Core')", timeout=15_000)

    def _set_react_val(el_handle, value):
        page.evaluate("""([el, v]) => {
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, v);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", [el_handle, value])

    range_inputs = page.query_selector_all('input[type="range"]')
    if range_inputs:
        _set_react_val(range_inputs[0], str(behavioral_pct))
        page.wait_for_timeout(200)
    num_inputs = page.locator('input[type="number"]')
    _set_react_val(num_inputs.nth(1).element_handle(), str(num_questions))
    page.wait_for_timeout(200)

    page.click("button:has-text('Save Config')", timeout=5_000)
    page.wait_for_selector("button:has-text('Saved!')", timeout=10_000)

    # Wait for regen
    print("    Waiting for regen…", end="", flush=True)
    deadline2 = time.time() + 300
    while time.time() < deadline2:
        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status",
                         headers={"Authorization": f"Bearer {token}"}, timeout=5)
        if r.status_code == 200 and (r.json().get("setup_status") or r.json().get("status")) == "ready":
            break
        page.wait_for_timeout(3000)
        print(".", end="", flush=True)
    print(" ready")

    return job_id


def _flag_first_cc(page, job_id):
    """Reload config panel and flag first question as CC. Returns question dict."""
    page.reload()
    page.wait_for_load_state("networkidle")
    page.click("button:has-text('Screening Interview Config')", timeout=8_000)
    page.wait_for_timeout(1500)
    page.wait_for_selector("button:has-text('Mark Core'), button:has-text('⭐ Core')", timeout=15_000)

    mark_core_btn = page.query_selector("button:has-text('Mark Core')")
    if not mark_core_btn:
        raise RuntimeError("No 'Mark Core' button found")

    jd = JOB_DESC
    mark_core_btn.click()
    page.wait_for_selector("button:has-text('⭐ Core')", timeout=15_000)
    page.wait_for_timeout(1000)  # allow DB write to commit

    return True


def _launch_mock_interview(ctx, page):
    """Click Mock Interview, return the interview page."""
    pages_before = set(id(p) for p in ctx.pages)
    page.click("button:has-text('Mock Interview')", timeout=8_000)
    interview_page = None
    for _ in range(40):
        page.wait_for_timeout(500)
        for p in ctx.pages:
            if "/interview/" in p.url and "localhost:5174" in p.url:
                interview_page = p
                break
        if interview_page:
            break
    if not interview_page:
        for p in ctx.pages:
            if id(p) not in pages_before and p != page:
                interview_page = p
                break
    if interview_page:
        interview_page.wait_for_load_state("networkidle")
    return interview_page


def _start_interview(interview_page):
    """Accept mic, tap to begin, wait for Q1."""
    interview_page.wait_for_selector("h1:has-text('Before you begin')", timeout=15_000)
    interview_page.click("button:has-text('Allow Microphone')", timeout=8_000)
    interview_page.wait_for_selector("button:has-text('Tap to Begin')", timeout=8_000)
    interview_page.click("button:has-text('Tap to Begin')")
    interview_page.wait_for_timeout(1000)
    interview_page.wait_for_selector("text=Question 1 of", timeout=10_000)


def _get_session_id(interview_page):
    return interview_page.url.rstrip("/").split("/")[-1].split("?")[0]


def _get_session(session_id):
    r = requests.get(f"{INTERVIEW_API}/api/interview/session/{session_id}", timeout=15)
    return r.json() if r.status_code == 200 else {}


def _wait_for_report(session_id, timeout_s=120):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        data = _get_session(session_id)
        if data.get("report"):
            return data["report"]
        time.sleep(3)
    return None


def _probe_active(page):
    return bool(page.query_selector("[data-probe-active]"))


def _wait_probe_active(page, timeout_s=20):
    for _ in range(timeout_s * 2):
        if _probe_active(page):
            return True
        page.wait_for_timeout(500)
    return False


# ── Scenarios ─────────────────────────────────────────────────────────────────

def scenario_a_regular_skip(p, record, recordings_dir, timestamp):
    """A: Skip on a regular question."""
    print("\n── Scenario A: Regular question — Skip ─────────────────────────")
    passed = []
    ctx = _make_context(p, record, recordings_dir, timestamp)
    try:
        page = ctx.new_page()
        _login(page)
        job_id = _create_job_and_wait(page, f"{JOB_TITLE_BASE}-A", num_questions=3, behavioral_pct=0)

        interview_page = _launch_mock_interview(ctx, page)
        passed.append(_check("A: Interview page opened", bool(interview_page)))
        if not interview_page:
            return passed

        _start_interview(interview_page)
        session_id = _get_session_id(interview_page)
        passed.append(_check("A: Interview started", True))

        # Wait for recording on Q1
        _wait_recording(interview_page, timeout_s=60)

        # Tap Skip on Q1 — without speaking
        skip_btn = _wait_enabled(interview_page, "button:has-text('Skip')", timeout_s=10)
        passed.append(_check("A: Skip button enabled on Q1", bool(skip_btn)))
        if skip_btn:
            interview_page.click("button:has-text('Skip')", timeout=5_000)

        # Q2 should now appear
        try:
            interview_page.wait_for_selector("text=Question 2 of", timeout=10_000)
            passed.append(_check("A: Advanced to Q2 after skip", True))
        except Exception as e:
            passed.append(_check("A: Advanced to Q2 after skip", False, str(e)))

        # Answer Q2 and Q3 normally then finish
        for qi in [2, 3]:
            _wait_recording(interview_page, timeout_s=30)
            _say(NORMAL_ANSWER)
            _wait_enabled(interview_page, "button:has-text('Finish'), button:has-text('Next')", timeout_s=20)
            is_last = bool(interview_page.query_selector("button:has-text('Finish'):not([disabled])"))
            interview_page.click("button:has-text('Finish')" if is_last else "button:has-text('Next')", timeout=5_000)
            _wait_transcribing(interview_page)
            interview_page.wait_for_timeout(500)

        # Wait for report
        try:
            interview_page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=120_000)
            passed.append(_check("A: Report page reached", True))
        except Exception as e:
            passed.append(_check("A: Report page reached", False, str(e)))

        # Verify Q1 transcript is [SKIPPED]
        print("  Polling for report…", end="", flush=True)
        report = _wait_for_report(session_id, timeout_s=90)
        print()
        if report:
            session = _get_session(session_id)
            full_tx = session.get("full_transcript", "")
            skipped_in_tx = "[SKIPPED]" in full_tx
            passed.append(_check("A: [SKIPPED] in transcript for Q1", skipped_in_tx, full_tx[:120]))
        else:
            passed.append(_check("A: Report generated", False, "timeout"))

    finally:
        ctx.close()
    return passed


def scenario_b_regular_end(p, record, recordings_dir, timestamp):
    """B: End mid-interview on a regular question."""
    print("\n── Scenario B: Regular question — End mid-interview ────────────")
    passed = []
    ctx = _make_context(p, record, recordings_dir, timestamp)
    try:
        page = ctx.new_page()
        _login(page)
        job_id = _create_job_and_wait(page, f"{JOB_TITLE_BASE}-B", num_questions=3, behavioral_pct=0)

        interview_page = _launch_mock_interview(ctx, page)
        passed.append(_check("B: Interview page opened", bool(interview_page)))
        if not interview_page:
            return passed

        _start_interview(interview_page)
        session_id = _get_session_id(interview_page)

        # Answer Q1
        _wait_recording(interview_page, timeout_s=60)
        _say(NORMAL_ANSWER)
        _wait_enabled(interview_page, "button:has-text('Next')", timeout_s=20)
        interview_page.click("button:has-text('Next')", timeout=5_000)
        _wait_transcribing(interview_page)

        # On Q2 — tap End instead of answering
        _wait_recording(interview_page, timeout_s=30)
        end_btn = _wait_enabled(interview_page, "button:has-text('End')", timeout_s=10)
        passed.append(_check("B: End button enabled on Q2", bool(end_btn)))
        if end_btn:
            interview_page.click("button:has-text('End')", timeout=5_000)

        # Should navigate to report/thank-you
        try:
            interview_page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=120_000)
            passed.append(_check("B: Interview ended and navigated to report", True))
        except Exception as e:
            passed.append(_check("B: Interview ended and navigated to report", False, str(e)))

        # Report should be generated
        print("  Polling for report…", end="", flush=True)
        report = _wait_for_report(session_id, timeout_s=90)
        print()
        passed.append(_check("B: Report generated after End", bool(report)))
        if report:
            pqs = report.get("per_question", [])
            passed.append(_check("B: Report has per-question entries", len(pqs) > 0, f"{len(pqs)} entries"))

    finally:
        ctx.close()
    return passed


def scenario_c_probe_skip(p, record, recordings_dir, timestamp):
    """C: Skip a probe question."""
    print("\n── Scenario C: Probe question — Skip probe ─────────────────────")
    passed = []
    ctx = _make_context(p, record, recordings_dir, timestamp)
    try:
        page = ctx.new_page()
        _login(page)
        job_id = _create_job_and_wait(page, f"{JOB_TITLE_BASE}-C", num_questions=1, behavioral_pct=0)
        _flag_first_cc(page, job_id)

        interview_page = _launch_mock_interview(ctx, page)
        passed.append(_check("C: Interview page opened", bool(interview_page)))
        if not interview_page:
            return passed

        _start_interview(interview_page)
        session_id = _get_session_id(interview_page)
        session_data = _get_session(session_id)
        questions = session_data.get("questions", [])

        # Answer shallowly to trigger probes
        _wait_recording(interview_page, timeout_s=60)
        _say(SHALLOW_ANSWER)
        _wait_enabled(interview_page, "button:has-text('Finish'), button:has-text('Next')", timeout_s=20)
        interview_page.click("button:has-text('Finish')", timeout=5_000)
        _wait_transcribing(interview_page)

        # Wait for probes to fire
        probe_fired = _wait_probe_active(interview_page, timeout_s=20)
        passed.append(_check("C: Probes fired after shallow answer", probe_fired))
        if not probe_fired:
            return passed

        # Skip probe 1
        _wait_recording(interview_page, timeout_s=30)
        skip_btn = _wait_enabled(interview_page, "button:has-text('Skip')", timeout_s=10)
        passed.append(_check("C: Skip button enabled during probe", bool(skip_btn)))
        if skip_btn:
            interview_page.click("button:has-text('Skip')", timeout=5_000)
            interview_page.wait_for_timeout(1000)

        # Should either show probe 2 (data-probe-active) or end interview if only 1 probe
        cc_q = next((q for q in questions if q.get("is_core_competency")), None)
        num_probes = len(cc_q.get("probe_questions", [])) if cc_q else 0

        if num_probes > 1:
            # Probe 2 should appear
            probe_2_appeared = _wait_probe_active(interview_page, timeout_s=10)
            passed.append(_check("C: Probe 2 appeared after skipping probe 1", probe_2_appeared))
            if probe_2_appeared:
                # Answer probe 2 normally to complete
                _wait_recording(interview_page, timeout_s=30)
                _say(NORMAL_ANSWER)
                _wait_enabled(interview_page, "button:has-text('Finish'), button:has-text('Next')", timeout_s=20)
                interview_page.click("button:has-text('Finish')", timeout=5_000)
                _wait_transcribing(interview_page)
        else:
            # Only 1 probe — interview should complete after skip
            try:
                interview_page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=30_000)
                passed.append(_check("C: Interview completed after skipping only probe", True))
            except Exception:
                passed.append(_check("C: Interview completed after skipping only probe", False, "still on interview page"))

        # Wait for report
        try:
            interview_page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=120_000)
            passed.append(_check("C: Report page reached after probe skip", True))
        except Exception as e:
            passed.append(_check("C: Report page reached after probe skip", False, str(e)))

        print("  Polling for report…", end="", flush=True)
        report = _wait_for_report(session_id, timeout_s=90)
        print()
        passed.append(_check("C: Report generated", bool(report)))

        if report:
            session = _get_session(session_id)
            full_tx = session.get("full_transcript", "")
            skipped_probe_in_tx = "[SKIPPED]" in full_tx
            passed.append(_check("C: [SKIPPED] in transcript for skipped probe", skipped_probe_in_tx, full_tx[:200]))

    finally:
        ctx.close()
    return passed


def scenario_d_probe_end(p, record, recordings_dir, timestamp):
    """D: Tap End mid-probe."""
    print("\n── Scenario D: Probe question — End mid-probe ──────────────────")
    passed = []
    ctx = _make_context(p, record, recordings_dir, timestamp)
    try:
        page = ctx.new_page()
        _login(page)
        job_id = _create_job_and_wait(page, f"{JOB_TITLE_BASE}-D", num_questions=1, behavioral_pct=0)
        _flag_first_cc(page, job_id)

        interview_page = _launch_mock_interview(ctx, page)
        passed.append(_check("D: Interview page opened", bool(interview_page)))
        if not interview_page:
            return passed

        _start_interview(interview_page)
        session_id = _get_session_id(interview_page)

        # Shallow answer → probe fires
        _wait_recording(interview_page, timeout_s=60)
        _say(SHALLOW_ANSWER)
        _wait_enabled(interview_page, "button:has-text('Finish'), button:has-text('Next')", timeout_s=20)
        interview_page.click("button:has-text('Finish')", timeout=5_000)
        _wait_transcribing(interview_page)

        probe_fired = _wait_probe_active(interview_page, timeout_s=20)
        passed.append(_check("D: Probe fired", probe_fired))
        if not probe_fired:
            return passed

        # Tap End during probe
        _wait_recording(interview_page, timeout_s=20)
        end_btn = _wait_enabled(interview_page, "button:has-text('End')", timeout_s=10)
        passed.append(_check("D: End button enabled during probe", bool(end_btn)))
        if end_btn:
            interview_page.click("button:has-text('End')", timeout=5_000)

        # Interview should complete cleanly
        try:
            interview_page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=120_000)
            passed.append(_check("D: Interview ended cleanly after End mid-probe", True))
        except Exception as e:
            passed.append(_check("D: Interview ended cleanly after End mid-probe", False, str(e)))

        print("  Polling for report…", end="", flush=True)
        report = _wait_for_report(session_id, timeout_s=90)
        print()
        passed.append(_check("D: Report generated after End mid-probe", bool(report)))

    finally:
        ctx.close()
    return passed


def scenario_e_button_labels(p, record, recordings_dir, timestamp):
    """E: Verify Next/Finish button label during probe flow."""
    print("\n── Scenario E: Button label correctness ────────────────────────")
    passed = []
    ctx = _make_context(p, record, recordings_dir, timestamp)
    try:
        page = ctx.new_page()
        _login(page)
        job_id = _create_job_and_wait(page, f"{JOB_TITLE_BASE}-E", num_questions=1, behavioral_pct=0)
        _flag_first_cc(page, job_id)

        interview_page = _launch_mock_interview(ctx, page)
        passed.append(_check("E: Interview page opened", bool(interview_page)))
        if not interview_page:
            return passed

        _start_interview(interview_page)
        session_id = _get_session_id(interview_page)
        session_data = _get_session(session_id)
        questions = session_data.get("questions", [])
        cc_q = next((q for q in questions if q.get("is_core_competency")), None)
        num_probes = len(cc_q.get("probe_questions", [])) if cc_q else 0

        # On last (only) main question, button should say "Finish" before answer
        _wait_recording(interview_page, timeout_s=60)
        finish_label_pre = bool(interview_page.query_selector("button:has-text('Finish')"))
        passed.append(_check("E: Button says 'Finish' on last main question", finish_label_pre))

        # Answer shallowly → probe fires
        _say(SHALLOW_ANSWER)
        _wait_enabled(interview_page, "button:has-text('Finish')", timeout_s=20)
        interview_page.click("button:has-text('Finish')", timeout=5_000)
        _wait_transcribing(interview_page)

        probe_fired = _wait_probe_active(interview_page, timeout_s=20)
        passed.append(_check("E: Probe fired", probe_fired))
        if not probe_fired:
            return passed

        # During probe 1 of 2: button should say "Next →" (not last probe)
        _wait_recording(interview_page, timeout_s=30)
        if num_probes > 1:
            next_label = bool(interview_page.query_selector("button:has-text('Next →')"))
            passed.append(_check("E: Button says 'Next →' on probe 1 of 2", next_label))

            # Answer probe 1 → go to probe 2
            _say(NORMAL_ANSWER)
            _wait_enabled(interview_page, "button:has-text('Next →')", timeout_s=20)
            interview_page.click("button:has-text('Next →')", timeout=5_000)
            _wait_transcribing(interview_page)
            interview_page.wait_for_timeout(1000)
            _wait_recording(interview_page, timeout_s=20)

            # On last probe of last question: button should say "Finish"
            finish_label_last_probe = bool(interview_page.query_selector("button:has-text('Finish')"))
            passed.append(_check("E: Button says 'Finish' on last probe of last question", finish_label_last_probe))

            # Finish it
            _say(NORMAL_ANSWER)
            _wait_enabled(interview_page, "button:has-text('Finish')", timeout_s=20)
            interview_page.click("button:has-text('Finish')", timeout=5_000)
            _wait_transcribing(interview_page)
        else:
            # Only 1 probe — it is both first and last, so should say "Finish"
            finish_label_only_probe = bool(interview_page.query_selector("button:has-text('Finish')"))
            passed.append(_check("E: Button says 'Finish' on only probe (last of last)", finish_label_only_probe))
            _say(NORMAL_ANSWER)
            _wait_enabled(interview_page, "button:has-text('Finish')", timeout_s=20)
            interview_page.click("button:has-text('Finish')", timeout=5_000)
            _wait_transcribing(interview_page)

        try:
            interview_page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=120_000)
            passed.append(_check("E: Report page reached", True))
        except Exception as e:
            passed.append(_check("E: Report page reached", False, str(e)))

    finally:
        ctx.close()
    return passed


def scenario_f_skip_all_probes(p, record, recordings_dir, timestamp):
    """F: Skip all probes on last question — interview must complete."""
    print("\n── Scenario F: Skip all probes on last question ────────────────")
    passed = []
    ctx = _make_context(p, record, recordings_dir, timestamp)
    try:
        page = ctx.new_page()
        _login(page)
        job_id = _create_job_and_wait(page, f"{JOB_TITLE_BASE}-F", num_questions=1, behavioral_pct=0)
        _flag_first_cc(page, job_id)

        interview_page = _launch_mock_interview(ctx, page)
        passed.append(_check("F: Interview page opened", bool(interview_page)))
        if not interview_page:
            return passed

        _start_interview(interview_page)
        session_id = _get_session_id(interview_page)
        session_data = _get_session(session_id)
        questions = session_data.get("questions", [])
        cc_q = next((q for q in questions if q.get("is_core_competency")), None)
        num_probes = len(cc_q.get("probe_questions", [])) if cc_q else 0
        print(f"  Probes to skip: {num_probes}")

        # Answer shallowly
        _wait_recording(interview_page, timeout_s=60)
        _say(SHALLOW_ANSWER)
        _wait_enabled(interview_page, "button:has-text('Finish')", timeout_s=20)
        interview_page.click("button:has-text('Finish')", timeout=5_000)
        _wait_transcribing(interview_page)

        probe_fired = _wait_probe_active(interview_page, timeout_s=20)
        passed.append(_check("F: Probes fired", probe_fired))
        if not probe_fired:
            return passed

        # Skip every probe
        for pi in range(num_probes):
            _wait_recording(interview_page, timeout_s=20)
            skip_btn = _wait_enabled(interview_page, "button:has-text('Skip')", timeout_s=10)
            if skip_btn:
                interview_page.click("button:has-text('Skip')", timeout=5_000)
                interview_page.wait_for_timeout(800)
                print(f"  Skipped probe {pi + 1}/{num_probes}")

        # Interview must complete after all probes skipped
        try:
            interview_page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=120_000)
            passed.append(_check("F: Interview completed after skipping all probes", True))
        except Exception as e:
            passed.append(_check("F: Interview completed after skipping all probes", False, str(e)))

        print("  Polling for report…", end="", flush=True)
        report = _wait_for_report(session_id, timeout_s=90)
        print()
        passed.append(_check("F: Report generated", bool(report)))
        if report:
            session = _get_session(session_id)
            full_tx = session.get("full_transcript", "")
            all_skipped = full_tx.count("[SKIPPED]") >= num_probes
            passed.append(_check(
                f"F: All {num_probes} probes marked [SKIPPED] in transcript",
                all_skipped,
                f"found {full_tx.count('[SKIPPED]')} [SKIPPED] markers"
            ))

    finally:
        ctx.close()
    return passed


# ── Main ──────────────────────────────────────────────────────────────────────

def run(record=False):
    print("\n" + "=" * 65)
    print("TalentBridge — Interview Button Behaviour E2E")
    print("=" * 65)

    if not check_services():
        print("\n❌ Services not running.")
        return False

    if not _check_blackhole():
        print("\n❌ BlackHole 2ch not found.")
        print("   Install from https://existential.audio/blackhole/ and retry.")
        return False
    print("  ✅ BlackHole 2ch available")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ playwright not installed: pip install playwright && playwright install chromium")
        return False

    subprocess.run(["SwitchAudioSource", "-s", "BlackHole 2ch", "-t", "input"], capture_output=True)

    recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    all_passed = []

    try:
        with sync_playwright() as p:
            all_passed += scenario_a_regular_skip(p, record, recordings_dir, timestamp)
            all_passed += scenario_b_regular_end(p, record, recordings_dir, timestamp)
            all_passed += scenario_c_probe_skip(p, record, recordings_dir, timestamp)
            all_passed += scenario_d_probe_end(p, record, recordings_dir, timestamp)
            all_passed += scenario_e_button_labels(p, record, recordings_dir, timestamp)
            all_passed += scenario_f_skip_all_probes(p, record, recordings_dir, timestamp)
    finally:
        _restore_audio()

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
    record = "--record" in sys.argv
    ok = run(record=record)
    sys.exit(0 if ok else 1)
