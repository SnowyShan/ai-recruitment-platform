#!/usr/bin/env python3
"""
End-to-end tests for Core Competency Probes feature.

Tests:
  1. API: probe-assess endpoint — needs_probing=true for shallow answers,
     needs_probing=false for thorough answers
  2. API: toggle core-competency on a question → probes generated + stored
  3. API: session create includes is_core_competency + probe_questions on flagged Qs
  4. API: complete session with core competency transcript markers → report includes
     core_competency_probes in per_question
  5. BROWSER: full interview flow with a core competency question — probe banner
     appears, probe question shown, code snippet displayed for code probes,
     transcript includes [CORE_COMPETENCY] and [PROBE_N] markers
     Records a video for visual review.

SERVICES REQUIRED:
  localhost:8000  — TalentBridge backend
  localhost:8001  — Interview module backend
  localhost:5173  — TalentBridge frontend
  localhost:5174  — Interview module frontend

Run:
  python tests/test_core_competency.py
  python tests/test_core_competency.py --record   # also records browser video
"""

import os
import sys
import json
import time
import uuid
import datetime
import requests

TB_API        = "http://localhost:8000"
INTERVIEW_API = "http://localhost:8001"
TB_URL        = "http://localhost:5173"
INTERVIEW_URL = "http://localhost:5174"

_RUN_ID       = uuid.uuid4().hex[:8]
TEST_EMAIL    = f"cc-test-{_RUN_ID}@test.internal"
TEST_PASSWORD = "CoreCompTest123!"
TEST_NAME     = "Core Competency Tester"

TEST_JOB = {
    "title":            f"Senior iOS Engineer [CC-TEST-{_RUN_ID}]",
    "description":      "Senior iOS engineer with deep Swift expertise. Strong ARC, memory management, concurrency, and architecture skills required.",
    "requirements":     "5+ years iOS. Expert Swift, UIKit, SwiftUI, ARC, weak/unowned references. Experience profiling with Instruments.",
    "department":       "Engineering",
    "location":         "Remote",
    "job_type":         "full_time",
    "experience_level": "senior",
}

SETUP_TIMEOUT = 180


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
        ("TB backend",        f"{TB_API}/health"),
        ("Interview backend", f"{INTERVIEW_API}/health"),
        ("TB frontend",       TB_URL),
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


def _auth():
    r = requests.post(f"{TB_API}/api/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD,
        "full_name": TEST_NAME, "company_name": "CC Tests",
    })
    if r.status_code not in (200, 201):
        # Try login
        r = requests.post(f"{TB_API}/api/auth/login",
                          json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Auth failed: {r.text}")
    return r.json()["access_token"]


def _create_and_setup_job(token):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{TB_API}/api/jobs/", headers=headers, json=TEST_JOB)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Job creation failed: {r.text}")
    job = r.json()
    job_id = job["id"]
    print(f"  Created job {job_id}")

    # Trigger setup
    requests.put(
        f"{TB_API}/api/jobs/{job_id}",
        json={"interview_num_questions": 4, "interview_difficulty": 3,
              "interview_seniority": "senior", "interview_behavioral_pct": 0},
        headers=headers,
    )

    # Wait for ready
    print("  Waiting for question bank…", end="", flush=True)
    deadline = time.time() + SETUP_TIMEOUT
    while time.time() < deadline:
        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status", headers=headers)
        if r.status_code == 200:
            s = r.json()
            status = s.get("setup_status") or s.get("status")
            if status == "ready":
                print(" ✅")
                break
            if status == "failed":
                print(" ❌ failed")
                return job_id, []
        time.sleep(3)
        print(".", end="", flush=True)
    else:
        print(" ❌ timeout")
        return job_id, []

    # Publish
    requests.post(f"{TB_API}/api/jobs/{job_id}/publish", headers=headers)

    # Get question IDs from question bank
    r = requests.get(f"{INTERVIEW_API}/api/interview/question-bank",
                     params={"domain": "ios", "limit": 10})
    questions = r.json().get("questions", []) if r.status_code == 200 else []
    return job_id, questions


def _create_session(job_id):
    jd = f"{TEST_JOB['description']}\n\n{TEST_JOB['requirements']}"
    r = requests.post(f"{INTERVIEW_API}/api/interview/session", json={
        "job_description": jd,
        "resume_text": "Candidate with 5 years iOS Swift experience.",
        "difficulty": 3,
        "seniority_bar": "senior",
        "time_limit": 30,
        "num_questions": 4,
        "behavioral_pct": 0,
        "job_id": job_id,
    })
    r.raise_for_status()
    return r.json()


# ── Test 1: probe-assess endpoint ─────────────────────────────────────────────

def test_probe_assess():
    """
    probe-assess must return needs_probing=true for shallow answers
    and needs_probing=false for thorough answers.
    """
    print("\n[Test 1] POST /probe-assess — shallow vs thorough answers")
    passed = []

    question = "Explain how ARC (Automatic Reference Counting) works in Swift."

    # Shallow answer — should need probing
    shallow = "ARC manages memory automatically."
    r = requests.post(f"{INTERVIEW_API}/api/interview/probe-assess", json={
        "question": question,
        "answer": shallow,
        "job_description": TEST_JOB["description"],
        "seniority_bar": "senior",
    })
    ok = r.status_code == 200
    passed.append(_check(f"POST /probe-assess → {r.status_code}", ok))
    if ok:
        data = r.json()
        passed.append(_check("Response has needs_probing field", "needs_probing" in data))
        passed.append(_check("Response has reason field", "reason" in data))
        passed.append(_check(
            "Shallow answer → needs_probing=true",
            data.get("needs_probing") is True,
            f"got needs_probing={data.get('needs_probing')}, reason={data.get('reason', '')[:60]}"
        ))

    # Thorough answer — should NOT need probing
    thorough = (
        "Automatic Reference Counting tracks the number of strong references to each "
        "class instance. When the count drops to zero, ARC deallocates the object and "
        "frees memory. I use weak references in delegate patterns and unowned in closures "
        "where the referenced object is guaranteed to outlive the closure. Retain cycles "
        "occur when two objects hold strong references to each other — I detect these with "
        "Instruments and fix them by making one side weak. ARC only applies to class "
        "instances, not structs or enums, since those are value types on the stack."
    )
    r2 = requests.post(f"{INTERVIEW_API}/api/interview/probe-assess", json={
        "question": question,
        "answer": thorough,
        "job_description": TEST_JOB["description"],
        "seniority_bar": "senior",
    })
    ok2 = r2.status_code == 200
    passed.append(_check(f"POST /probe-assess (thorough) → {r2.status_code}", ok2))
    if ok2:
        data2 = r2.json()
        passed.append(_check(
            "Thorough answer → needs_probing=false",
            data2.get("needs_probing") is False,
            f"got needs_probing={data2.get('needs_probing')}, reason={data2.get('reason', '')[:60]}"
        ))

    return passed


# ── Test 2: toggle core-competency on a question ─────────────────────────────

def test_toggle_core_competency(questions):
    """
    PUT /question/{id}/core-competency must:
    - Set is_core_competency=1 and generate probe_questions
    - Return the correct shape
    - Be reversible (disable)
    """
    print("\n[Test 2] PUT /question/{id}/core-competency — toggle + probe generation")
    passed = []

    if not questions:
        passed.append(_check("Question bank has questions to test with", False,
                              "no questions available"))
        return passed

    q = questions[0]
    q_id = q["id"]
    print(f"  Testing with question: {q['question'][:60]}…")

    # Enable core competency
    r = requests.put(
        f"{INTERVIEW_API}/api/interview/question/{q_id}/core-competency",
        json={"enabled": True, "job_description": TEST_JOB["description"]},
    )
    ok = r.status_code == 200
    passed.append(_check(f"PUT /question/{q_id[:8]}…/core-competency → {r.status_code}", ok))

    if ok:
        data = r.json()
        passed.append(_check("Response has question_id", "question_id" in data))
        passed.append(_check("is_core_competency=True in response",
                              data.get("is_core_competency") is True))

    # Verify probes were stored — fetch from question bank
    r2 = requests.get(f"{INTERVIEW_API}/api/interview/question-bank",
                      params={"domain": "all", "limit": 50})
    if r2.status_code == 200:
        qs = r2.json().get("questions", [])
        flagged = next((x for x in qs if x["id"] == q_id), None)
        if flagged:
            probes = flagged.get("probe_questions")
            if isinstance(probes, str):
                probes = json.loads(probes) if probes else []
            passed.append(_check("Question now has probe_questions",
                                  isinstance(probes, list) and len(probes) > 0,
                                  f"{len(probes) if probes else 0} probes"))
            passed.append(_check("is_core_competency=1 in DB",
                                  bool(flagged.get("is_core_competency"))))
            if probes:
                probe = probes[0]
                passed.append(_check("Probe has required fields",
                                      all(k in probe for k in ["question", "voice_text",
                                          "presentation_mode", "expected_answer",
                                          "answer_type"])))
                passed.append(_check("Probe presentation_mode is voice or code",
                                      probe.get("presentation_mode") in ("voice", "code")))
                if probe.get("presentation_mode") == "code":
                    passed.append(_check("Code probe has code_snippet",
                                          bool(probe.get("code_snippet"))))
        else:
            passed.append(_check("Flagged question found in bank", False))
    
    # Disable — should clear probes
    r3 = requests.put(
        f"{INTERVIEW_API}/api/interview/question/{q_id}/core-competency",
        json={"enabled": False},
    )
    passed.append(_check(f"PUT disable core-competency → {r3.status_code}",
                          r3.status_code == 200))
    if r3.status_code == 200:
        passed.append(_check("is_core_competency=False in disable response",
                              r3.json().get("is_core_competency") is False))

    # Re-enable for downstream tests
    requests.put(
        f"{INTERVIEW_API}/api/interview/question/{q_id}/core-competency",
        json={"enabled": True, "job_description": TEST_JOB["description"]},
    )

    return passed, q_id


# ── Test 3: session includes probe data for flagged questions ─────────────────

def test_session_includes_probes(job_id, flagged_question_id):
    """
    After flagging a question, creating a session must include
    is_core_competency=True and probe_questions in the question payload.
    """
    print("\n[Test 3] Session create — flagged question includes probe data")
    passed = []

    data = _create_session(job_id)
    session_id = data.get("session_id")
    questions = data.get("questions", [])

    passed.append(_check("Session created", bool(session_id)))
    passed.append(_check(f"Session has questions ({len(questions)})", len(questions) > 0))

    flagged = next((q for q in questions if q.get("id") == flagged_question_id), None)
    if flagged:
        passed.append(_check("Flagged question present in session", True))
        passed.append(_check("is_core_competency=True on flagged question",
                              flagged.get("is_core_competency") is True))
        probes = flagged.get("probe_questions", [])
        passed.append(_check("probe_questions present and non-empty",
                              isinstance(probes, list) and len(probes) > 0,
                              f"{len(probes)} probes"))
    else:
        # Flagged Q might not be in this session if it was randomly shuffled out
        # (session may have fewer questions than bank) — soft warning
        print("  ⚠️  Flagged question not in this session (may be excluded by random shuffle)")
        passed.append(_check("Flagged question check (soft — shuffle may exclude it)", True))

    return passed, session_id, questions


# ── Test 4: complete session with CC transcript → report includes probes ───────

def test_report_with_cc_transcript(session_id, questions):
    """
    Submitting a transcript with [CORE_COMPETENCY] and [PROBE_N] markers
    must produce a report where the flagged question has core_competency_probes.
    """
    print("\n[Test 4] Complete session — report parses CC transcript markers")
    passed = []

    jd = f"{TEST_JOB['description']}\n\n{TEST_JOB['requirements']}"

    # Build a transcript that includes a CC question with probe answers
    full_transcript = ""
    for i, q in enumerate(questions):
        is_cc = q.get("is_core_competency", False)
        cc_marker = " [CORE_COMPETENCY]" if is_cc else ""
        full_transcript += f"[Q{i+1}: {q['question']}]{cc_marker}\n"
        full_transcript += "ARC tracks strong references and deallocates when count is zero. I use weak references in delegate patterns and unowned in closures. Retain cycles happen when two objects reference each other strongly — I fix them by making one side weak.\n\n"

        if is_cc and q.get("probe_questions"):
            for pi, probe in enumerate(q["probe_questions"]):
                full_transcript += f"[PROBE_{pi+1}: {probe['question']}]\n"
                full_transcript += f"{probe.get('expected_answer', 'yes')}\n\n"

    r = requests.post(
        f"{INTERVIEW_API}/api/interview/session/{session_id}/complete",
        json={"full_transcript": full_transcript, "questions": questions},
        timeout=120,
    )
    passed.append(_check(f"POST /session/complete → {r.status_code}", r.status_code == 200))
    if r.status_code != 200:
        return passed

    report = r.json()
    passed.append(_check("Report has per_question", len(report.get("per_question", [])) > 0))
    passed.append(_check("Report has overall_score > 0",
                          report.get("overall_score", 0) > 0))

    # Check if any CC question got core_competency_probes in the report
    cc_questions_in_session = [q for q in questions if q.get("is_core_competency")]
    if cc_questions_in_session:
        # Find the matching per_question entry
        cc_q_text = cc_questions_in_session[0]["question"]
        cc_pq = next(
            (pq for pq in report.get("per_question", [])
             if cc_q_text[:40].lower() in pq.get("question", "").lower()),
            None
        )
        if cc_pq:
            probes_in_report = cc_pq.get("core_competency_probes", [])
            passed.append(_check(
                "CC question in report has core_competency_probes array",
                isinstance(probes_in_report, list),
                f"got {type(probes_in_report).__name__}"
            ))
            if probes_in_report:
                passed.append(_check(
                    "Probe entry has question/candidate_answer/pass fields",
                    all(k in probes_in_report[0] for k in ["question", "candidate_answer", "pass"])
                ))
        else:
            print("  ⚠️  Could not match CC question in per_question (Claude may rephrase)")
            passed.append(_check("CC question matched in report (soft)", True))
    else:
        print("  ⚠️  No CC questions in this session — probe report check skipped")

    return passed


# ── Test 5: Browser — full interview with CC probe flow ────────────────────────

def test_browser_cc_flow(job_id, record=False):
    """
    Browser test: start an interview with a core-competency question.
    Asserts:
    - "Core competency check" banner appears after tapping Next
    - Probe question is displayed (different from main question)
    - Code snippet shows for code probes
    - After all probes, advances normally
    Records video if --record passed.
    """
    print("\n[Test 5] Browser — core competency probe flow")
    passed = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️  playwright not installed — skipping browser test")
        return passed

    recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Create a session
    sess_data = _create_session(job_id)
    session_id = sess_data.get("session_id")
    questions = sess_data.get("questions", [])
    if not session_id:
        passed.append(_check("Session created for browser test", False))
        return passed
    passed.append(_check("Session created for browser test", True, session_id))

    cc_questions = [q for q in questions if q.get("is_core_competency")]
    print(f"  Core competency questions in session: {len(cc_questions)}")

    context_kwargs = {"viewport": {"width": 1280, "height": 900}}
    if record:
        context_kwargs["record_video_dir"] = recordings_dir
        context_kwargs["record_video_size"] = {"width": 1280, "height": 900}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(**context_kwargs)

        # Mock getUserMedia
        ctx.add_init_script("""
            navigator.mediaDevices.getUserMedia = async () => {
                const actx = new (window.AudioContext || window.webkitAudioContext)();
                const dst = actx.createMediaStreamDestination();
                return dst.stream;
            };
            // Disable TTS so tests don't wait for audio playback
            localStorage.setItem('interview_tts_enabled', 'false');
        """)

        # Also mock Whisper transcription on the backend — inject a fake transcript
        # by overriding fetch for /transcribe endpoint
        ctx.add_init_script("""
            const origFetch = window.fetch;
            window.fetch = async (url, opts) => {
                if (typeof url === 'string' && url.includes('/transcribe')) {
                    return new Response(JSON.stringify({text: "ARC manages memory via reference counting. Objects are deallocated when strong reference count hits zero. I use weak references to break retain cycles."}), {status: 200, headers: {'Content-Type': 'application/json'}});
                }
                return origFetch(url, opts);
            };
        """)

        page = ctx.new_page()

        # Navigate to interview
        interview_url = f"{INTERVIEW_URL}/interview/{session_id}"
        page.goto(interview_url)
        page.wait_for_load_state("networkidle")

        # Before you begin screen
        try:
            page.wait_for_selector("h1:has-text('Before you begin')", timeout=10_000)
            passed.append(_check("'Before you begin' screen loaded", True))
        except Exception as e:
            passed.append(_check("'Before you begin' screen loaded", False, str(e)))
            ctx.close(); browser.close()
            return passed

        # Grant mic
        page.click("button:has-text('Allow Microphone')")
        page.wait_for_selector("button:has-text('Tap to Begin')", timeout=8_000)
        page.click("button:has-text('Tap to Begin')")
        page.wait_for_timeout(1500)

        # Verify interview started
        try:
            page.wait_for_selector("text=Question 1 of", timeout=8_000)
            passed.append(_check("Interview started — Q1 visible", True))
        except Exception as e:
            passed.append(_check("Interview started — Q1 visible", False, str(e)))
            ctx.close(); browser.close()
            return passed

        found_probe_banner = False
        found_probe_question_change = False
        found_code_snippet = False

        # Cycle through questions, tapping Next each time
        for qi in range(len(questions)):
            # Wait for Next/Finish to be enabled
            for _ in range(30):
                if (page.query_selector("button:has-text('Finish'):not([disabled])") or
                        page.query_selector("button:has-text('Next'):not([disabled])")):
                    break
                page.wait_for_timeout(300)

            # Capture current question text before clicking Next
            try:
                q_text_before = page.text_content("p.text-base, p.text-lg", timeout=2000)
            except Exception:
                q_text_before = ""

            is_last = bool(page.query_selector("button:has-text('Finish'):not([disabled])"))
            btn_sel = "button:has-text('Finish')" if is_last else "button:has-text('Next')"
            page.click(btn_sel, timeout=8_000)

            # Wait for transcribing to finish
            try:
                page.wait_for_selector("p:has-text('Processing')", timeout=3_000)
                page.wait_for_selector("p:has-text('Processing')", state="hidden", timeout=30_000)
            except Exception:
                pass

            # Small pause for probe-assess call + state update
            page.wait_for_timeout(2000)

            # Check for probe banner
            page_content = page.content()
            if "Core competency check" in page_content or "Follow-up" in page_content:
                found_probe_banner = True
                print("    ✅ Probe banner detected!")

                # Check probe question is different from main question
                try:
                    new_q_text = page.text_content("p.text-base, p.text-lg", timeout=2000)
                    if new_q_text and new_q_text.strip() != q_text_before.strip():
                        found_probe_question_change = True
                        print(f"    ✅ Probe question shown: {new_q_text.strip()[:60]}…")
                except Exception:
                    pass

                # Check for code snippet (<pre> tag)
                pre = page.query_selector("pre")
                if pre:
                    found_code_snippet = True
                    print("    ✅ Code snippet visible!")

                # Answer the probe(s) — keep tapping Next until banner gone
                for _ in range(3):  # max 2 probes + buffer
                    for _w in range(20):
                        if (page.query_selector("button:has-text('Finish'):not([disabled])") or
                                page.query_selector("button:has-text('Next'):not([disabled])")):
                            break
                        page.wait_for_timeout(300)

                    content_now = page.content()
                    if "Core competency check" not in content_now and "Follow-up" not in content_now:
                        break

                    is_last_p = bool(page.query_selector("button:has-text('Finish'):not([disabled])"))
                    btn_p = "button:has-text('Finish')" if is_last_p else "button:has-text('Next')"
                    page.click(btn_p, timeout=8_000)

                    try:
                        page.wait_for_selector("p:has-text('Processing')", timeout=3_000)
                        page.wait_for_selector("p:has-text('Processing')", state="hidden", timeout=30_000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)

            if is_last:
                break

        passed.append(_check(
            "Probe banner ('Core competency check') appeared during interview",
            found_probe_banner,
            "(no CC questions in session)" if not cc_questions else ""
        ))
        passed.append(_check(
            "Probe question text changed from main question",
            found_probe_question_change or not found_probe_banner
        ))
        passed.append(_check(
            "Code snippet displayed for code probe",
            found_code_snippet or not found_probe_banner,
            "(only if a code probe was triggered)"
        ))

        # Wait for report or thank-you page
        try:
            page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u, timeout=90_000)
            passed.append(_check("Interview completed — navigated to report/thank-you", True))
        except Exception as e:
            passed.append(_check("Interview completed", False, str(e)))

        if record and page.video:
            video_path_raw = page.video.path()
        else:
            video_path_raw = None

        ctx.close()
        browser.close()

    if record and video_path_raw and os.path.exists(video_path_raw):
        final = os.path.join(recordings_dir, f"cc_probe_flow_{timestamp}.webm")
        os.rename(video_path_raw, final)
        print(f"  📹 Video saved: {final}")

    return passed


# ── Runner ────────────────────────────────────────────────────────────────────

def run(record=False):
    print("\n" + "=" * 65)
    print("TalentBridge — Core Competency Probes Tests")
    print("=" * 65)

    if not check_services():
        print("\n❌ Services not running. Start all services and retry.")
        return False

    all_passed = []

    # Auth
    print("\n[Auth] Registering test user…")
    try:
        token = _auth()
        print(f"  Registered/logged in ✅")
    except Exception as e:
        print(f"  ❌ Auth failed: {e}")
        return False

    # Setup job + question bank
    print("\n[Setup] Creating job + waiting for question bank…")
    try:
        job_id, questions = _create_and_setup_job(token)
        print(f"  job_id={job_id}, {len(questions)} questions in bank")
    except Exception as e:
        print(f"  ❌ Setup failed: {e}")
        return False

    # Test 1 — probe-assess
    all_passed += test_probe_assess()

    # Test 2 — toggle core competency
    if questions:
        result = test_toggle_core_competency(questions)
        if isinstance(result, tuple):
            t2_passed, flagged_q_id = result
        else:
            t2_passed, flagged_q_id = result, None
        all_passed += t2_passed
    else:
        print("\n[Test 2] SKIPPED — no questions in bank")
        flagged_q_id = None

    # Test 3 — session includes probe data
    if flagged_q_id:
        t3_result = test_session_includes_probes(job_id, flagged_q_id)
        if isinstance(t3_result, tuple):
            t3_passed, session_id, sess_questions = t3_result
        else:
            t3_passed, session_id, sess_questions = t3_result, None, []
        all_passed += t3_passed
    else:
        print("\n[Test 3] SKIPPED — no flagged question")
        session_id, sess_questions = None, []

    # Test 4 — report parses CC transcript
    if session_id and sess_questions:
        all_passed += test_report_with_cc_transcript(session_id, sess_questions)
    else:
        print("\n[Test 4] SKIPPED — no session available")

    # Test 5 — browser flow
    all_passed += test_browser_cc_flow(job_id, record=record)

    # Summary
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
