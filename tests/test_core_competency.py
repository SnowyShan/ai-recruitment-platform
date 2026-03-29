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
SHALLOW_ANSWER = "I don't know."

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

            # Click Create Job button (the primary action button in the page header,
            # not sidebar nav links). Use strict button selector.
            page.click("button.btn-primary:has-text('Create Job')", timeout=8_000)
            page.wait_for_selector("h2:has-text('Create New Job')", timeout=8_000)
            passed.append(_check("Create Job modal opened", True))

            # Fill the form
            page.fill('input[name="title"]', JOB_TITLE)
            page.fill('input[name="department"]', "Engineering")
            page.fill('input[name="location"]', "Remote")
            page.fill('textarea[name="description"]', JOB_DESC)
            page.fill('textarea[name="requirements"]', JOB_REQS)
            passed.append(_check("Job form filled", True))

            # Submit — the modal's submit button says "Create Job"
            page.click('button[type="submit"].btn-primary:has-text("Create Job")',
                       timeout=5_000)

            # After submit, modal closes and jobs list reloads.
            # Wait for the modal to disappear then find the new job by title.
            try:
                page.wait_for_selector("h2:has-text('Create New Job')",
                                       state="hidden", timeout=10_000)
            except Exception:
                pass
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1000)

            # Find the new job card by title and click View / the job title link
            job_link = None
            for _ in range(10):
                job_link = page.query_selector(f"a[href*='/jobs/']:has-text('{JOB_TITLE[:30]}')")
                if not job_link:
                    # Try finding via card text then the View link nearby
                    card = page.query_selector(f"text={JOB_TITLE[:30]}")
                    if card:
                        job_link = card.evaluate_handle(
                            "el => el.closest('[href]') || el.closest('div').querySelector('a[href*=\"/jobs/\"]')"
                        )
                        if job_link.as_element():
                            break
                if job_link:
                    break
                page.wait_for_timeout(1000)

            if not job_link or not job_link.as_element() if hasattr(job_link, 'as_element') else not job_link:
                # Fallback: get the job ID from the API and navigate directly
                try:
                    token = _get_token()
                    r = requests.get(f"{TB_API}/api/jobs/",
                                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
                    jobs = r.json() if r.status_code == 200 else []
                    new_job = next((j for j in jobs if JOB_TITLE[:20] in j.get("title", "")), None)
                    if new_job:
                        page.goto(f"{TB_URL}/jobs/{new_job['id']}")
                        page.wait_for_load_state("networkidle")
                        passed.append(_check("Navigated to job detail page (via API fallback)", True, page.url))
                    else:
                        passed.append(_check("Found newly created job", False, "not found in job list"))
                        ctx.close()
                        return False
                except Exception as e:
                    passed.append(_check("Navigated to job detail page", False, str(e)))
                    ctx.close()
                    return False
            else:
                job_link.click()
                try:
                    page.wait_for_url(lambda u: "/jobs/" in u and u != f"{TB_URL}/jobs",
                                      timeout=10_000)
                except Exception:
                    pass
                passed.append(_check("Navigated to job detail page", True, page.url))

            job_url = page.url
            job_id  = job_url.rstrip("/").split("/")[-1].split("?")[0]
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

            # ── Step 5: Set num_questions=1, behavioral_pct=0 then Save ──
            # One question, no behavioral split — that one question IS the CC one.
            # No lottery, no polling needed.
            print("\n[Step 5] Set 1 question / 0% behavioral and Save Config")

            def _set_react_val(el_handle, value):
                page.evaluate("""([el, v]) => {
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, v);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""", [el_handle, value])

            # Set behavioral_pct=0 FIRST (range slider), then num_questions=1.
            # Order matters: behavioral is capped at Math.max(1, round(n * pct/100)).
            # With pct=0, that becomes Math.max(1, 0) = 1... but the component
            # uses behavioral_pct directly in the hint display, and pct=0 makes
            # num_behavioral=0 in create_session. So pct=0 first, then n=1 → 1 technical.
            range_inputs = page.query_selector_all('input[type="range"]')
            if range_inputs:
                _set_react_val(range_inputs[0], "0")
                page.wait_for_timeout(200)

            # Number inputs: [0]=duration, [1]=num_questions
            num_inputs = page.locator('input[type="number"]')
            _set_react_val(num_inputs.nth(1).element_handle(), "1")
            page.wait_for_timeout(200)

            hint = page.locator("p.text-xs.text-slate-400").first.text_content()
            print(f"  Config: {hint.strip()}")

            page.wait_for_timeout(300)
            page.click("button:has-text('Save Config')", timeout=5_000)

            try:
                page.wait_for_selector("button:has-text('Saved!')", timeout=10_000)
                passed.append(_check("Config saved — 'Saved!' appeared", True))
            except Exception as e:
                passed.append(_check("Config saved — 'Saved!' appeared", False, str(e)))

            # Wait for re-generation to complete
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

            # Reload page to get fresh question list after regen
            page.reload()
            page.wait_for_load_state("networkidle")

            # ── Step 6: Mark a question as Core Competency (post-regen) ──
            print("\n[Step 6] Mark a question as Core Competency")

            # Expand config panel again after reload
            page.click("button:has-text('Screening Interview Config')", timeout=8_000)
            page.wait_for_timeout(1500)

            # Wait for fresh question list
            try:
                page.wait_for_selector("button:has-text('Mark Core'), button:has-text('\u2b50 Core')",
                                       timeout=15_000)
                passed.append(_check("Fresh question list loaded after re-gen", True))
            except Exception as e:
                passed.append(_check("Fresh question list loaded after re-gen", False, str(e)))
                ctx.close()
                return False

            # Now that JobDetail.jsx fetches questions scoped to this job (job_id param),
            # all "Mark Core" buttons in the UI belong to this job's active question set.
            # Just use the first one.
            mark_core_btn = page.query_selector("button:has-text('Mark Core')")

            if not mark_core_btn:
                passed.append(_check("Found 'Mark Core' button for active job question", False))
                ctx.close()
                return False

            try:
                question_text = mark_core_btn.evaluate(
                    "el => el.closest('div').querySelector('span.truncate')?.textContent || ''"
                )
                print(f"  Flagging: {question_text[:70]}…")
            except Exception:
                pass

            mark_core_btn.click()

            # Wait for ⭐ Core badge — this means the API call completed and probes generated
            try:
                page.wait_for_selector("button:has-text('\u2b50 Core')", timeout=15_000)
                passed.append(_check("'⭐ Core' badge appeared after toggle", True))
            except Exception as e:
                passed.append(_check("'⭐ Core' badge appeared after toggle", False, str(e)))

            # Wait for probe generation to finish — the toggle call generates probes
            # server-side (Haiku). Poll the /probe-assess endpoint as a liveness check,
            # then wait a moment for the DB write to commit.
            print("  Waiting for probe generation to complete…", end="", flush=True)
            for _ in range(20):
                # The ⭐ Core badge is shown immediately on toggle; probe generation
                # happens in the same synchronous request. If badge is visible, probes exist.
                if page.query_selector("button:has-text('\u2b50 Core')"):
                    break
                page.wait_for_timeout(500)
                print(".", end="", flush=True)
            print()
            # Give the DB write one extra tick to commit before session creation
            page.wait_for_timeout(1000)

            # ── Step 7: Click Mock Interview ──────────────────────────────
            print("\n[Step 7] Click Mock Interview button")

            # Mock Interview opens a blank window, creates a session via fetch,
            # then sets newWindow.location.href to localhost:5174/interview/{id}.
            # Playwright may catch the blank window before it navigates.
            # Strategy: click the button, then wait for any page in context with /interview/ URL.
            pages_before = set(id(p) for p in ctx.pages)
            page.click("button:has-text('Mock Interview')", timeout=8_000)

            # Wait up to 20s for the interview page to appear at localhost:5174
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
                # Fallback: check if any new page appeared at all
                for p in ctx.pages:
                    if id(p) not in pages_before and p != page:
                        interview_page = p
                        break

            if interview_page:
                interview_page.wait_for_load_state("networkidle")

            passed.append(_check("Interview tab opened", bool(interview_page)))
            print(f"  Interview URL: {interview_page.url}")

            is_interview = "/interview/" in interview_page.url
            passed.append(_check("Interview URL is /interview/{session_id}", is_interview,
                                  interview_page.url))
            if not is_interview:
                ctx.close()
                return False

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
                        if interview_page.query_selector("[data-probe-active]"):
                            break
                        print(".", end="", flush=True)
                    print()

                    if interview_page.query_selector("[data-probe-active]"):
                        probe_banner_appeared = True
                        print("    ✅ Probe banner detected!")

                        # Answer each probe
                        probe_questions = q.get("probe_questions", [])
                        for pi, probe in enumerate(probe_questions):
                            print(f"    Probe {pi+1}: '{probe['question'][:60]}…'")

                            # Check for code snippet on this probe
                            if interview_page.query_selector("pre"):
                                code_snippet_shown = True
                                print("    ✅ Code snippet visible!")

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
                        if not interview_page.query_selector("[data-probe-active]"):
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
            # Code snippet: only required if at least one code probe exists in the session
            has_code_probe = any(
                p.get("presentation_mode") == "code"
                for q in questions if q.get("is_core_competency")
                for p in q.get("probe_questions", [])
            )
            passed.append(_check(
                "Code snippet shown for code probe",
                code_snippet_shown or not has_code_probe or not probe_banner_appeared,
                "(no code probe in this session)" if not has_code_probe else ""
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
            # Poll until report is populated (Claude Sonnet may take 15-30s)
            print("  Polling for report…", end="", flush=True)
            report_data = None
            for _ in range(30):
                time.sleep(3)
                try:
                    r = requests.get(f"{INTERVIEW_API}/api/interview/session/{session_id}", timeout=15)
                    if r.status_code == 200 and r.json().get("report"):
                        report_data = r.json().get("report")
                        break
                except Exception:
                    pass
                print(".", end="", flush=True)
            print()
            if report_data:
                cc_pqs = [
                    pq for pq in report_data.get("per_question", [])
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
                passed.append(_check("Report generated within timeout", False, "report still null after 90s"))

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
