#!/usr/bin/env python3
"""
End-to-end test for Core Competency Probes — fully browser-driven.

Everything after login is driven through the real UI. No direct API calls
for job creation, question flagging, session creation, or interview setup.
The browser is the user.

What is real:
  - Browser login and job creation via the TB frontend
  - Question bank generation (TB backend calls interview module)
  - "Mark Core" toggle clicked in the Screening Interview Config UI
  - "Save Config" clicked in the UI
  - "Mock Interview" button clicked in the UI — creates session via UI flow
  - TTS: browser plays questions via OpenAI TTS
  - Mic recording: MediaRecorder captures BlackHole 2ch loopback input
  - Whisper transcription: real /transcribe endpoint
  - probe-assess: real Haiku call on the actual transcript
  - Report generation: real Claude Sonnet

What is mocked:
  - Mic input: `say -a "BlackHole 2ch"` speaks answers into the browser mic
    via BlackHole virtual loopback (no real human, but real audio pipeline)
  - Mic permission dialog: --use-fake-ui-for-media-stream Chrome flag
    (auto-approves without replacing the audio device)

FAILS (does not skip) if BlackHole is not installed.

REQUIREMENTS:
  BlackHole 2ch: https://existential.audio/blackhole/
  SwitchAudioSource: brew install switchaudio-osx
  playwright: pip install playwright && playwright install chromium

SERVICES REQUIRED:
  localhost:8000  — TalentBridge backend
  localhost:8001  — Interview module backend
  localhost:5173  — TalentBridge frontend
  localhost:5174  — Interview module frontend

Run:
  python tests/test_core_competency.py
  python tests/test_core_competency.py --record
"""

import os
import sys
import json
import time
import uuid
import shutil
import datetime
import subprocess
import requests

TB_URL        = "http://localhost:5173"
INTERVIEW_URL = "http://localhost:5174"
TB_API        = "http://localhost:8000"
INTERVIEW_API = "http://localhost:8001"

_RUN_ID       = uuid.uuid4().hex[:8]
TEST_EMAIL    = "e2e-test@gmail.com"
TEST_PASSWORD = "E2eTestPass123!"
TEST_NAME     = "E2E Test Recruiter"

JOB_TITLE = f"Senior iOS Engineer [CC-E2E-{_RUN_ID}]"
JOB_DESC  = (
    "Senior iOS engineer with deep Swift expertise. "
    "Strong ARC memory management, retain cycles, weak/unowned references, "
    "concurrency with GCD and async/await, and architecture skills required."
)
JOB_REQS  = "5+ years iOS. Expert Swift, UIKit, SwiftUI, ARC, Instruments."

# Deliberately shallow — one sentence. Haiku must return needs_probing=true.
SHALLOW_ANSWER = "ARC manages memory automatically."

# Normal answer for non-CC questions.
NORMAL_ANSWER = (
    "In my iOS work I use UIKit and SwiftUI. "
    "I structure apps with MVVM, use dependency injection for testability, "
    "and profile with Instruments. "
    "I prefer async await over GCD for new code."
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check(label, cond, detail=""):
    mark = "✅" if cond else "❌"
    line = f"  {mark} {label}"
    if detail:
        line += f"  [{detail}]"
    print(line)
    return cond


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
    result = subprocess.run(
        ["say", "-a", "BlackHole 2ch", ""],
        capture_output=True, timeout=3
    )
    return result.returncode == 0


def _restore_audio():
    subprocess.run(
        ["SwitchAudioSource", "-s", "MacBook Pro Microphone", "-t", "input"],
        capture_output=True
    )


def _say(text):
    """Speak text into BlackHole → browser mic."""
    subprocess.run(["say", "-r", "170", "-a", "BlackHole 2ch", text], check=False)


def _wait_enabled(page, selector, timeout_s=30):
    """Wait until a button matching selector is not disabled."""
    for _ in range(timeout_s * 2):
        el = page.query_selector(f"{selector}:not([disabled])")
        if el:
            return el
        page.wait_for_timeout(500)
    return None


def _wait_recording(page, timeout_s=60):
    """Wait until the 'Recording' indicator is visible and 'Speaking' is not."""
    print(".", end="", flush=True)
    for _ in range(timeout_s * 2):
        content = page.content()
        if "Recording" in content and "Speaking…" not in content:
            return True
        page.wait_for_timeout(500)
        print(".", end="", flush=True)
    return False


def _dismiss_new_tab(context, original_page):
    """
    Mock Interview opens a new tab. Wait for it and return the new page.
    """
    for _ in range(20):
        pages = context.pages
        if len(pages) > 1:
            new_page = [p for p in pages if p != original_page][-1]
            return new_page
        time.sleep(0.5)
    return None


# ── The test ──────────────────────────────────────────────────────────────────

def run(record=False):
    print("\n" + "=" * 65)
    print("TalentBridge — Core Competency Probes E2E (browser-driven)")
    print("=" * 65)

    if not check_services():
        print("\n❌ Services not running.")
        return False

    # Require BlackHole — fail hard, not skip
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

    # Set BlackHole as system audio INPUT
    subprocess.run(["SwitchAudioSource", "-s", "BlackHole 2ch", "-t", "input"],
                   capture_output=True)

    recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    passed = []
    profile_dir = "/tmp/cc_e2e_browser_profile"
    shutil.rmtree(profile_dir, ignore_errors=True)

    context_kwargs = {"viewport": {"width": 1280, "height": 900}}
    if record:
        context_kwargs["record_video_dir"] = recordings_dir
        context_kwargs["record_video_size"] = {"width": 1280, "height": 900}

    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                args=["--use-fake-ui-for-media-stream"],
                **context_kwargs,
            )
            page = ctx.new_page()

            # ── Step 1: Login ─────────────────────────────────────────────
            print("\n[Step 1] Login")
            page.goto(f"{TB_URL}/login")
            page.wait_for_load_state("networkidle")
            page.fill('input[type="email"]', TEST_EMAIL)
            page.fill('input[type="password"]', TEST_PASSWORD)
            page.click('button[type="submit"]')

            # Wait for redirect to dashboard or jobs
            for _ in range(20):
                if "/dashboard" in page.url or "/jobs" in page.url:
                    break
                page.wait_for_timeout(500)

            on_dashboard = "/dashboard" in page.url or "/jobs" in page.url
            passed.append(_check("Logged in — on dashboard/jobs", on_dashboard, page.url))
            if not on_dashboard:
                ctx.close()
                return False

            # ── Step 2: Create job via UI ─────────────────────────────────
            print("\n[Step 2] Create job via UI")
            page.goto(f"{TB_URL}/jobs")
            page.wait_for_load_state("networkidle")

            # Click Create Job button
            page.click("button:has-text('Create Job'), button:has-text('New Job'), button:has-text('Post Job')",
                       timeout=8_000)
            page.wait_for_selector("h2:has-text('Create New Job')", timeout=8_000)
            passed.append(_check("Create Job modal opened", True))

            # Fill the form
            page.fill('input[name="title"]', JOB_TITLE)
            page.fill('input[name="department"]', "Engineering")
            page.fill('input[name="location"]', "Remote")
            page.fill('textarea[name="description"]', JOB_DESC)
            page.fill('textarea[name="requirements"]', JOB_REQS)
            passed.append(_check("Job form filled", True))

            # Submit
            page.click('button[type="submit"]:has-text("Create"), button[type="submit"]:has-text("Post"), form button[type="submit"]',
                       timeout=5_000)

            # Should navigate to job detail page
            try:
                page.wait_for_url(lambda u: "/jobs/" in u and u != f"{TB_URL}/jobs",
                                  timeout=15_000)
                passed.append(_check("Navigated to job detail page", True, page.url))
            except Exception as e:
                passed.append(_check("Navigated to job detail page", False, str(e)))
                ctx.close()
                return False

            job_url = page.url
            job_id  = job_url.rstrip("/").split("/")[-1]
            print(f"  Job ID: {job_id}")

            # ── Step 3: Wait for question bank generation ─────────────────
            print("\n[Step 3] Waiting for question bank generation (TB → Interview module)…", end="", flush=True)
            deadline = time.time() + 300  # 5 min max
            setup_ready = False
            while time.time() < deadline:
                content = page.content()
                # Setup complete when generating banner gone and no spinner in config header
                generating = "Generating interview questions" in content
                if not generating:
                    # Double-check via API
                    try:
                        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status",
                                        headers={"Authorization": f"Bearer {_get_token()}"}, timeout=5)
                        if r.status_code == 200:
                            status = r.json().get("setup_status") or r.json().get("status")
                            if status == "ready":
                                setup_ready = True
                                break
                    except Exception:
                        pass
                page.wait_for_timeout(3000)
                print(".", end="", flush=True)

            print()
            passed.append(_check("Question bank ready (setup_status=ready)", setup_ready))
            if not setup_ready:
                ctx.close()
                return False

            # Reload so the question list populates
            page.reload()
            page.wait_for_load_state("networkidle")

            # ── Step 4: Expand Screening Interview Config ─────────────────
            print("\n[Step 4] Expand Screening Interview Config")
            page.click("button:has-text('Screening Interview Config')", timeout=8_000)
            page.wait_for_timeout(1500)

            # Wait for question list to load inside config panel
            try:
                page.wait_for_selector("button:has-text('Mark Core'), button:has-text('⭐ Core')",
                                       timeout=15_000)
                passed.append(_check("Question list loaded in config panel", True))
            except Exception as e:
                passed.append(_check("Question list loaded in config panel", False, str(e)))
                ctx.close()
                return False

            # ── Step 5: Mark first question as Core Competency ────────────
            print("\n[Step 5] Mark first question as Core Competency")
            mark_core_btn = page.query_selector("button:has-text('Mark Core')")
            if not mark_core_btn:
                passed.append(_check("Found 'Mark Core' button", False, "no untagged questions found"))
                ctx.close()
                return False

            # Capture the question text next to the button (for logging)
            try:
                question_text = mark_core_btn.evaluate(
                    "el => el.closest('div').querySelector('span.truncate')?.textContent || ''"
                )
                print(f"  Flagging: {question_text[:70]}…")
            except Exception:
                pass

            mark_core_btn.click()
            page.wait_for_timeout(2000)  # API call + re-render

            # Verify the button now shows ⭐ Core
            try:
                page.wait_for_selector("button:has-text('⭐ Core'), button:has-text('\u2b50 Core')",
                                       timeout=8_000)
                passed.append(_check("'⭐ Core' badge appeared after toggle", True))
            except Exception as e:
                passed.append(_check("'⭐ Core' badge appeared after toggle", False, str(e)))

            # ── Step 6: Save Config ───────────────────────────────────────
            print("\n[Step 6] Save Config")
            page.click("button:has-text('Save Config')", timeout=5_000)

            # Wait for "Saved!" confirmation
            try:
                page.wait_for_selector("button:has-text('Saved!')", timeout=10_000)
                passed.append(_check("Config saved — 'Saved!' appeared", True))
            except Exception as e:
                passed.append(_check("Config saved — 'Saved!' appeared", False, str(e)))

            # Wait for re-generation to complete (Save Config triggers new setup)
            print("  Waiting for re-generation after save…", end="", flush=True)
            deadline2 = time.time() + 300
            regen_ready = False
            while time.time() < deadline2:
                content = page.content()
                if "Generating interview questions" not in content:
                    try:
                        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status",
                                        headers={"Authorization": f"Bearer {_get_token()}"}, timeout=5)
                        if r.status_code == 200:
                            status = r.json().get("setup_status") or r.json().get("status")
                            if status == "ready":
                                regen_ready = True
                                break
                    except Exception:
                        pass
                page.wait_for_timeout(3000)
                print(".", end="", flush=True)
            print()
            passed.append(_check("Re-generation complete after save", regen_ready))
            if not regen_ready:
                ctx.close()
                return False

            # ── Step 7: Click Mock Interview ──────────────────────────────
            print("\n[Step 7] Click Mock Interview button")

            # Make sure config panel is still open (may have collapsed)
            if not page.query_selector("button:has-text('Mock Interview')"):
                page.click("button:has-text('Screening Interview Config')", timeout=5_000)
                page.wait_for_timeout(1000)

            # Mock Interview opens a new tab
            with ctx.expect_page() as new_page_info:
                page.click("button:has-text('Mock Interview')", timeout=8_000)

            interview_page = new_page_info.value
            interview_page.wait_for_load_state("networkidle")

            # Add BlackHole loopback init script to interview tab
            # (can't inject before navigation since it's a new tab opened by the app)
            # We rely on --use-fake-ui-for-media-stream set at context level.

            passed.append(_check("Interview tab opened", bool(interview_page)))
            print(f"  Interview URL: {interview_page.url}")

            # Verify it's an interview session URL
            is_interview = "/interview/" in interview_page.url
            passed.append(_check("Interview URL is /interview/{session_id}", is_interview,
                                  interview_page.url))
            if not is_interview:
                ctx.close()
                return False

            # Extract session_id from URL for later report check
            session_id = interview_page.url.rstrip("/").split("/")[-1].split("?")[0]
            print(f"  Session ID: {session_id}")

            # ── Step 8: Start interview ───────────────────────────────────
            print("\n[Step 8] Start interview")

            try:
                interview_page.wait_for_selector("h1:has-text('Before you begin')",
                                                  state="visible", timeout=15_000)
                passed.append(_check("'Before you begin' screen loaded", True))
            except Exception as e:
                passed.append(_check("'Before you begin' screen loaded", False, str(e)))
                ctx.close()
                return False

            interview_page.click("button:has-text('Allow Microphone')", timeout=8_000)
            interview_page.wait_for_selector("button:has-text('Tap to Begin')",
                                              state="visible", timeout=8_000)
            interview_page.click("button:has-text('Tap to Begin')")
            interview_page.wait_for_timeout(1000)

            try:
                interview_page.wait_for_selector("text=Question 1 of",
                                                  state="visible", timeout=10_000)
                passed.append(_check("Interview started — Question 1 visible", True))
            except Exception as e:
                passed.append(_check("Interview started", False, str(e)))
                ctx.close()
                return False

            # Fetch question list from session to know which are CC
            questions = []
            try:
                r = requests.get(f"{INTERVIEW_API}/api/interview/session/{session_id}", timeout=10)
                if r.status_code == 200:
                    questions = r.json().get("questions", [])
            except Exception:
                pass

            cc_indices = [i for i, q in enumerate(questions) if q.get("is_core_competency")]
            print(f"  Questions: {len(questions)}, CC indices: {cc_indices}")
            for i, q in enumerate(questions):
                tag = " [CC]" if q.get("is_core_competency") else ""
                print(f"    Q{i+1}{tag}: {q['question'][:65]}…")

            # ── Step 9: Answer questions ──────────────────────────────────
            print("\n[Step 9] Answering questions via BlackHole")

            probe_banner_appeared = False
            code_snippet_shown    = False
            probe_mode_cleared    = False

            for qi in range(max(len(questions), 1)):
                q = questions[qi] if qi < len(questions) else {}
                is_cc = q.get("is_core_competency", False)
                tag   = " [CC]" if is_cc else ""
                print(f"\n  Q{qi+1}{tag}: {q.get('question','')[:60]}…")

                # Wait for Recording indicator (TTS finished)
                print("    Waiting for Recording indicator…", end="", flush=True)
                recording = _wait_recording(interview_page, timeout_s=60)
                print(" recording" if recording else " (timeout)")

                # Speak answer
                answer_text = SHALLOW_ANSWER if is_cc else NORMAL_ANSWER
                print(f"    Speaking: '{answer_text[:60]}'")
                _say(answer_text)

                # Wait for Next/Finish enabled
                btn = _wait_enabled(interview_page,
                                    "button:has-text('Finish'), button:has-text('Next')",
                                    timeout_s=20)

                is_last = bool(interview_page.query_selector(
                    "button:has-text('Finish'):not([disabled])"))
                interview_page.click(
                    "button:has-text('Finish')" if is_last else "button:has-text('Next')",
                    timeout=8_000
                )
                print(f"    Clicked {'Finish' if is_last else 'Next'}")

                # Wait for Whisper
                try:
                    interview_page.wait_for_selector("p:has-text('Processing')", timeout=5_000)
                    interview_page.wait_for_selector("p:has-text('Processing')",
                                                      state="hidden", timeout=60_000)
                    print("    Transcribed ✓")
                except Exception:
                    pass

                # For CC question: wait for probe-assess + state update
                if is_cc:
                    print("    Waiting for probe-assess…", end="", flush=True)
                    page.wait_for_timeout(500)
                    for _ in range(10):
                        interview_page.wait_for_timeout(500)
                        content = interview_page.content()
                        if "Core competency check" in content or "Follow-up" in content:
                            break
                        print(".", end="", flush=True)
                    print()

                    content = interview_page.content()
                    if "Core competency check" in content or "Follow-up" in content:
                        probe_banner_appeared = True
                        print("    ✅ Probe banner detected!")

                        if interview_page.query_selector("pre"):
                            code_snippet_shown = True
                            print("    ✅ Code snippet visible!")

                        # Answer each probe
                        probe_questions = q.get("probe_questions", [])
                        for pi, probe in enumerate(probe_questions):
                            print(f"    Probe {pi+1}: '{probe['question'][:60]}…'")

                            print("    Waiting for Recording…", end="", flush=True)
                            _wait_recording(interview_page, timeout_s=30)
                            print(" recording")

                            probe_answer = probe.get("expected_answer", "yes")
                            print(f"    Speaking probe answer: '{probe_answer[:60]}'")
                            _say(probe_answer)

                            _wait_enabled(interview_page,
                                          "button:has-text('Finish'), button:has-text('Next')",
                                          timeout_s=20)
                            is_last_p = bool(interview_page.query_selector(
                                "button:has-text('Finish'):not([disabled])"))
                            interview_page.click(
                                "button:has-text('Finish')" if is_last_p else "button:has-text('Next')",
                                timeout=8_000
                            )

                            try:
                                interview_page.wait_for_selector("p:has-text('Processing')",
                                                                  timeout=5_000)
                                interview_page.wait_for_selector("p:has-text('Processing')",
                                                                  state="hidden", timeout=60_000)
                            except Exception:
                                pass
                            interview_page.wait_for_timeout(1500)

                        # Probe mode should be cleared
                        if "Core competency check" not in interview_page.content():
                            probe_mode_cleared = True
                            print("    ✅ Probe mode cleared — back to main questions")
                    else:
                        print(f"    Probe banner did NOT appear (needs_probing may be false for: '{answer_text}')")

                if is_last:
                    break

            passed.append(_check(
                "Probe banner appeared after shallow CC answer",
                probe_banner_appeared,
                "Haiku returned needs_probing=false — answer may need to be shorter" if not probe_banner_appeared else ""
            ))
            passed.append(_check(
                "Code snippet shown for code probe",
                code_snippet_shown or not probe_banner_appeared,
                "(only expected if a code probe was generated)"
            ))
            passed.append(_check(
                "Probe mode cleared after all probes answered",
                probe_mode_cleared or not probe_banner_appeared
            ))

            # ── Step 10: Wait for report ──────────────────────────────────
            print("\n[Step 10] Waiting for report generation…", end="", flush=True)
            try:
                interview_page.wait_for_url(
                    lambda u: "/report/" in u or "/thank-you" in u,
                    timeout=120_000
                )
                print(" ✅")
                passed.append(_check("Report page reached", True, interview_page.url))
            except Exception as e:
                print(" ❌")
                passed.append(_check("Report page reached", False, str(e)))

            # ── Step 11: Verify report has CC probe results ───────────────
            print("\n[Step 11] Verify report has core_competency_probes")
            time.sleep(3)
            try:
                r = requests.get(f"{INTERVIEW_API}/api/interview/session/{session_id}", timeout=15)
                if r.status_code == 200:
                    report = r.json().get("report")
                    if report:
                        cc_pqs = [
                            pq for pq in report.get("per_question", [])
                            if pq.get("core_competency_probes")
                        ]
                        passed.append(_check(
                            "Report has core_competency_probes in per_question",
                            len(cc_pqs) > 0,
                            f"{len(cc_pqs)} question(s) with probe results"
                        ))
                        if cc_pqs:
                            p0 = cc_pqs[0]["core_competency_probes"][0]
                            passed.append(_check(
                                "Probe has question/candidate_answer/pass fields",
                                all(k in p0 for k in ["question", "candidate_answer", "pass"]),
                                f"pass={p0.get('pass')}, answer='{p0.get('candidate_answer','')[:40]}'"
                            ))
                    else:
                        passed.append(_check("Report generated", False, "report is null"))
                else:
                    passed.append(_check(f"Session fetch → {r.status_code}", False))
            except Exception as e:
                passed.append(_check("Report check failed", False, str(e)))

            # Save video
            if record and interview_page.video:
                raw = interview_page.video.path()
            else:
                raw = None

            ctx.close()

            if record and raw and os.path.exists(raw):
                final = os.path.join(recordings_dir,
                                     f"cc_e2e_browser_{timestamp}.webm")
                os.rename(raw, final)
                print(f"\n  📹 Video saved: {final}")

    finally:
        _restore_audio()

    total  = len(passed)
    failed = sum(1 for p in passed if not p)
    print("\n" + "=" * 65)
    if failed == 0:
        print(f"✅  ALL {total} CHECKS PASSED")
    else:
        print(f"❌  {failed}/{total} CHECKS FAILED")
    print("=" * 65)

    return failed == 0


# ── Token helper (only used for setup-status polling during wait loops) ───────

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
    # Try register
    r = requests.post(f"{TB_API}/api/auth/register",
                      json={"email": TEST_EMAIL, "password": TEST_PASSWORD,
                            "full_name": TEST_NAME, "company_name": "E2E Tests"})
    _cached_token = r.json()["access_token"]
    return _cached_token


if __name__ == "__main__":
    record = "--record" in sys.argv
    ok = run(record=record)
    sys.exit(0 if ok else 1)
