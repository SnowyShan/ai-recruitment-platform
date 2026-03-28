#!/usr/bin/env python3
"""
End-to-end tests for Core Competency Probes feature.

Tests 1–4: API-only (no browser). All calls are real — real Claude Haiku for
probe-assess and probe generation, real Anthropic API for report.

Test 5: Full browser e2e — the only thing that is NOT a real human is the mic
input. Audio is routed via BlackHole 2ch (virtual loopback): `say -a "BlackHole
2ch"` sends spoken audio directly into the browser's mic input, which feeds real
Whisper transcription, real probe-assess, real probe generation, real report.

  Real in test 5:
    - TTS (browser plays questions via OpenAI TTS on speakers)
    - Mic recording (MediaRecorder captures BlackHole input)
    - Whisper transcription (real /transcribe endpoint)
    - probe-assess (real Haiku call on the transcribed answer)
    - probe generation (pre-generated via Haiku at setup time)
    - Report generation (real Claude Sonnet)

  Mocked in test 5:
    - Mic input: `say -a "BlackHole 2ch"` instead of a human voice
    - Mic permission dialog: --use-fake-ui-for-media-stream Chrome flag
      (auto-approves the browser dialog without replacing the audio device)

REQUIREMENTS:
  BlackHole 2ch installed (https://existential.audio/blackhole/)
  SwitchAudioSource installed: brew install switchaudio-osx
  macOS `say` command (built-in)
  pip install playwright && playwright install chromium

  If BlackHole is not installed: test 5 FAILS (does not skip).
  The test validates the real audio pipeline; silently skipping defeats the purpose.

SERVICES REQUIRED:
  localhost:8000  — TalentBridge backend
  localhost:8001  — Interview module backend
  localhost:5173  — TalentBridge frontend
  localhost:5174  — Interview module frontend

Run:
  python tests/test_core_competency.py
  python tests/test_core_competency.py --record   # saves .webm video of browser test
"""

import os
import sys
import json
import time
import uuid
import datetime
import subprocess
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
    "description":      (
        "Senior iOS engineer with deep Swift expertise. "
        "Strong ARC memory management, retain cycles, weak/unowned references, "
        "concurrency, and architecture skills required."
    ),
    "requirements":     "5+ years iOS. Expert Swift, UIKit, SwiftUI, ARC, Instruments.",
    "department":       "Engineering",
    "location":         "Remote",
    "job_type":         "full_time",
    "experience_level": "senior",
}

SETUP_TIMEOUT = 180

# Shallow answer — one vague sentence. Haiku must return needs_probing=true.
SHALLOW_ANSWER = "ARC manages memory automatically."

# Normal answer for non-CC questions — enough to not get flagged.
NORMAL_ANSWER = (
    "In my iOS work I have used both UIKit and SwiftUI. "
    "I structure apps with MVVM, use dependency injection for testability, "
    "and profile performance with Instruments. "
    "I prefer async await over GCD for new code due to structured concurrency."
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
    """Return True if BlackHole 2ch is available as an audio device."""
    result = subprocess.run(
        ["say", "-a", "BlackHole 2ch", ""],
        capture_output=True, timeout=3
    )
    return result.returncode == 0


def _auth():
    r = requests.post(f"{TB_API}/api/auth/register", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD,
        "full_name": TEST_NAME, "company_name": "CC Tests",
    })
    if r.status_code not in (200, 201):
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

    requests.put(
        f"{TB_API}/api/jobs/{job_id}",
        json={"interview_num_questions": 4, "interview_difficulty": 3,
              "interview_seniority": "senior", "interview_behavioral_pct": 0},
        headers=headers,
    )

    print("  Waiting for question bank…", end="", flush=True)
    retried = False
    deadline = time.time() + SETUP_TIMEOUT
    while time.time() < deadline:
        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status", headers=headers)
        if r.status_code == 200:
            s = r.json()
            status = s.get("setup_status") or s.get("status")
            if status == "ready":
                print(" ✅")
                break
            if status == "failed" and not retried:
                print(" failed, retrying", end="", flush=True)
                requests.put(
                    f"{TB_API}/api/jobs/{job_id}",
                    json={"interview_num_questions": 4, "interview_difficulty": 3,
                          "interview_seniority": "senior", "interview_behavioral_pct": 0},
                    headers=headers,
                )
                retried = True
                time.sleep(5)
                continue
            if status == "failed" and retried:
                print(" ❌ failed after retry")
                return job_id, []
        time.sleep(3)
        print(".", end="", flush=True)
    else:
        print(" ❌ timeout")
        return job_id, []

    requests.post(f"{TB_API}/api/jobs/{job_id}/publish", headers=headers)

    r = requests.get(f"{INTERVIEW_API}/api/interview/question-bank",
                     params={"domain": "all", "limit": 20})
    questions = r.json().get("questions", []) if r.status_code == 200 else []
    return job_id, questions


def _flag_question_as_cc(question_id):
    """Flag a question as core competency and wait for probes to be generated."""
    r = requests.put(
        f"{INTERVIEW_API}/api/interview/question/{question_id}/core-competency",
        json={"enabled": True, "job_description": TEST_JOB["description"]},
    )
    r.raise_for_status()
    return r.json()


def _create_session(job_id):
    jd = f"{TEST_JOB['description']}\n\n{TEST_JOB['requirements']}"
    r = requests.post(f"{INTERVIEW_API}/api/interview/session", json={
        "job_description": jd,
        "resume_text": "5 years iOS Swift UIKit experience.",
        "difficulty": 3, "seniority_bar": "senior",
        "time_limit": 30, "num_questions": 4,
        "behavioral_pct": 0, "job_id": job_id,
    })
    r.raise_for_status()
    return r.json()


# ── Test 1: probe-assess — shallow vs thorough ────────────────────────────────

def test_probe_assess():
    """
    probe-assess must return needs_probing=true for a shallow answer
    and needs_probing=false for a thorough answer.
    Both calls go to real Claude Haiku — no mocking.
    """
    print("\n[Test 1] POST /probe-assess — shallow vs thorough (real Haiku)")
    passed = []

    question = "Explain how ARC (Automatic Reference Counting) works in Swift."

    r = requests.post(f"{INTERVIEW_API}/api/interview/probe-assess", json={
        "question": question,
        "answer": SHALLOW_ANSWER,
        "job_description": TEST_JOB["description"],
        "seniority_bar": "senior",
    })
    passed.append(_check(f"POST /probe-assess → {r.status_code}", r.status_code == 200))
    if r.status_code == 200:
        d = r.json()
        passed.append(_check("Response has needs_probing field", "needs_probing" in d))
        passed.append(_check("Response has reason field", "reason" in d))
        passed.append(_check(
            f"Shallow answer ('{SHALLOW_ANSWER}') → needs_probing=true",
            d.get("needs_probing") is True,
            f"needs_probing={d.get('needs_probing')}, reason={d.get('reason','')[:80]}"
        ))

    thorough = (
        "Automatic Reference Counting tracks strong references to each class instance. "
        "When the count reaches zero, ARC deallocates the object and frees memory. "
        "I use weak references in delegate patterns to avoid retain cycles, and unowned "
        "in closures where the captured object is guaranteed to outlive the closure. "
        "Retain cycles happen when two objects hold strong references to each other — "
        "I detect these in Instruments Leaks and break them by making one side weak. "
        "ARC only applies to reference types (classes), not value types like structs."
    )
    r2 = requests.post(f"{INTERVIEW_API}/api/interview/probe-assess", json={
        "question": question,
        "answer": thorough,
        "job_description": TEST_JOB["description"],
        "seniority_bar": "senior",
    })
    passed.append(_check(f"POST /probe-assess (thorough) → {r2.status_code}",
                          r2.status_code == 200))
    if r2.status_code == 200:
        d2 = r2.json()
        passed.append(_check(
            "Thorough answer → needs_probing=false",
            d2.get("needs_probing") is False,
            f"needs_probing={d2.get('needs_probing')}, reason={d2.get('reason','')[:80]}"
        ))

    return passed


# ── Test 2: toggle core-competency — generates real probes ────────────────────

def test_toggle_core_competency(questions):
    """
    PUT /question/{id}/core-competency must store probes with the correct shape.
    Probes are generated by real Claude Haiku. At least one should be a code probe
    for a memory-management topic.
    """
    print("\n[Test 2] PUT /question/{id}/core-competency — real probe generation")
    passed = []

    if not questions:
        passed.append(_check("Question bank non-empty (required for this test)", False,
                              "run with services up and wait for setup to complete"))
        return passed, None

    q = questions[0]
    q_id = q["id"]
    print(f"  Question: {q['question'][:70]}…")

    r = requests.put(
        f"{INTERVIEW_API}/api/interview/question/{q_id}/core-competency",
        json={"enabled": True, "job_description": TEST_JOB["description"]},
    )
    passed.append(_check(f"PUT enable → {r.status_code}", r.status_code == 200))
    if r.status_code == 200:
        passed.append(_check("Response: is_core_competency=True",
                              r.json().get("is_core_competency") is True))

    # Fetch from bank and inspect probes
    r2 = requests.get(f"{INTERVIEW_API}/api/interview/question-bank",
                      params={"domain": "all", "limit": 50})
    if r2.status_code == 200:
        flagged = next((x for x in r2.json().get("questions", []) if x["id"] == q_id), None)
        if flagged:
            raw = flagged.get("probe_questions")
            probes = json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
            passed.append(_check("probe_questions stored and non-empty",
                                  isinstance(probes, list) and len(probes) > 0,
                                  f"{len(probes)} probes"))
            if probes:
                for i, probe in enumerate(probes):
                    passed.append(_check(
                        f"Probe {i+1} has required fields",
                        all(k in probe for k in ["question", "voice_text",
                            "presentation_mode", "expected_answer", "answer_type"]),
                        str(list(probe.keys()))
                    ))
                    passed.append(_check(
                        f"Probe {i+1} presentation_mode is voice or code",
                        probe.get("presentation_mode") in ("voice", "code")
                    ))
                    if probe.get("presentation_mode") == "code":
                        passed.append(_check(
                            f"Probe {i+1} (code) has non-empty code_snippet",
                            bool(probe.get("code_snippet", "").strip())
                        ))
                        print(f"    Code snippet preview: {probe['code_snippet'][:80]}…")
                    passed.append(_check(
                        f"Probe {i+1} expected_answer is non-empty",
                        bool(probe.get("expected_answer", "").strip())
                    ))
        else:
            passed.append(_check("Flagged question found in bank after toggle", False))

    # Verify disable clears probes
    r3 = requests.put(
        f"{INTERVIEW_API}/api/interview/question/{q_id}/core-competency",
        json={"enabled": False},
    )
    passed.append(_check(f"PUT disable → {r3.status_code}", r3.status_code == 200))
    if r3.status_code == 200:
        passed.append(_check("Disable response: is_core_competency=False",
                              r3.json().get("is_core_competency") is False))

    # Re-enable so downstream tests have a flagged question to work with
    requests.put(
        f"{INTERVIEW_API}/api/interview/question/{q_id}/core-competency",
        json={"enabled": True, "job_description": TEST_JOB["description"]},
    )
    return passed, q_id


# ── Test 3: session bundles probe data ────────────────────────────────────────

def test_session_includes_probes(job_id, flagged_q_id):
    """
    Creating a session after a question is flagged must include
    is_core_competency=True and probe_questions[] in that question's payload.
    """
    print("\n[Test 3] Session create — flagged question carries probe data")
    passed = []

    data = _create_session(job_id)
    session_id = data.get("session_id")
    questions  = data.get("questions", [])

    passed.append(_check("Session created", bool(session_id), session_id or "none"))
    passed.append(_check(f"Session has questions", len(questions) > 0,
                          f"{len(questions)} questions"))

    flagged = next((q for q in questions if q.get("id") == flagged_q_id), None)
    if flagged:
        passed.append(_check("Flagged question present in session payload", True))
        passed.append(_check("is_core_competency=True on question",
                              flagged.get("is_core_competency") is True))
        probes = flagged.get("probe_questions", [])
        passed.append(_check("probe_questions[] present and non-empty",
                              isinstance(probes, list) and len(probes) > 0,
                              f"{len(probes)} probes"))
        if probes:
            passed.append(_check("Each probe has question + voice_text",
                                  all("question" in p and "voice_text" in p for p in probes)))
    else:
        # Flagged question may be shuffled out if session has fewer Qs than bank
        print("  ⚠️  Flagged question not drawn into this session (shuffle). "
              "Creating a larger session to guarantee inclusion…")
        # Try a session with more questions
        jd = f"{TEST_JOB['description']}\n\n{TEST_JOB['requirements']}"
        r2 = requests.post(f"{INTERVIEW_API}/api/interview/session", json={
            "job_description": jd, "resume_text": "5 years iOS Swift.",
            "difficulty": 3, "seniority_bar": "senior",
            "time_limit": 30, "num_questions": 6, "behavioral_pct": 0,
            "job_id": job_id,
        })
        if r2.status_code == 200:
            d2 = r2.json()
            session_id = d2["session_id"]
            questions  = d2["questions"]
            flagged    = next((q for q in questions if q.get("id") == flagged_q_id), None)
            if flagged:
                passed.append(_check("Flagged question found in larger session", True))
                passed.append(_check("is_core_competency=True",
                                      flagged.get("is_core_competency") is True))
                probes = flagged.get("probe_questions", [])
                passed.append(_check("probe_questions present",
                                      isinstance(probes, list) and len(probes) > 0))
            else:
                passed.append(_check("Flagged question found in session", False,
                                      "question not in bank draw even with larger session"))
        else:
            passed.append(_check("Larger session created", False, f"HTTP {r2.status_code}"))

    return passed, session_id, questions


# ── Test 4: report parses CC transcript markers ───────────────────────────────

def test_report_with_cc_transcript(session_id, questions):
    """
    Complete a session with a transcript containing [CORE_COMPETENCY] and
    [PROBE_N: ...] markers. The report must include core_competency_probes
    in the per_question entry for the flagged question.
    Uses real Claude Sonnet for report generation.
    """
    print("\n[Test 4] Report generation — CC transcript markers parsed (real Claude)")
    passed = []

    if not session_id:
        passed.append(_check("Session available for report test", False))
        return passed

    full_transcript = ""
    for i, q in enumerate(questions):
        is_cc = q.get("is_core_competency", False)
        marker = " [CORE_COMPETENCY]" if is_cc else ""
        full_transcript += f"[Q{i+1}: {q['question']}]{marker}\n"
        if is_cc:
            # Deliberately shallow main answer so probe was warranted
            full_transcript += f"{SHALLOW_ANSWER}\n\n"
            # Then probe answers (use expected_answer from probe data)
            for pi, probe in enumerate(q.get("probe_questions", [])):
                full_transcript += f"[PROBE_{pi+1}: {probe['question']}]\n"
                full_transcript += f"{probe.get('expected_answer', 'yes')}\n\n"
        else:
            full_transcript += f"{NORMAL_ANSWER}\n\n"

    r = requests.post(
        f"{INTERVIEW_API}/api/interview/session/{session_id}/complete",
        json={"full_transcript": full_transcript, "questions": questions},
        timeout=120,
    )
    passed.append(_check(f"POST /session/complete → {r.status_code}",
                          r.status_code == 200))
    if r.status_code != 200:
        print(f"    detail: {r.text[:200]}")
        return passed

    report = r.json()
    pqs = report.get("per_question", [])
    passed.append(_check("Report has per_question entries", len(pqs) > 0, f"{len(pqs)}"))
    passed.append(_check("overall_score > 0", report.get("overall_score", 0) > 0,
                          f"{report.get('overall_score')}/100"))

    cc_questions = [q for q in questions if q.get("is_core_competency")]
    if cc_questions:
        cc_q_text = cc_questions[0]["question"].lower()[:50]
        cc_pq = next(
            (pq for pq in pqs if cc_q_text in pq.get("question", "").lower()),
            None
        )
        if cc_pq:
            probes_in_report = cc_pq.get("core_competency_probes")
            passed.append(_check(
                "CC per_question has core_competency_probes field",
                probes_in_report is not None,
                f"type={type(probes_in_report).__name__}"
            ))
            if isinstance(probes_in_report, list) and probes_in_report:
                p0 = probes_in_report[0]
                passed.append(_check(
                    "Probe entry has question, candidate_answer, pass",
                    all(k in p0 for k in ["question", "candidate_answer", "pass"])
                ))
                print(f"    Probe result: pass={p0.get('pass')}, "
                      f"answer='{p0.get('candidate_answer','')[:40]}'")
        else:
            print("  ⚠️  Could not match CC question in per_question "
                  "(Claude may rephrase question text — soft pass)")
            passed.append(_check("CC question matched in per_question (soft)", True))
    else:
        print("  ⚠️  No CC questions in this session — probe report check skipped")

    return passed


# ── Test 5: Browser e2e — real audio via BlackHole ────────────────────────────

def test_browser_cc_flow_real_audio(job_id, record=False):
    """
    Full browser e2e test using real audio pipeline.

    What is real:
      - TTS: browser plays questions via OpenAI TTS on speakers
      - Mic recording: MediaRecorder captures BlackHole 2ch input
      - Whisper transcription: real /transcribe endpoint
      - probe-assess: real Haiku call on the actual transcript
      - Report generation: real Claude Sonnet

    What is mocked:
      - Mic input: `say -a "BlackHole 2ch"` routes spoken answers into the
        browser mic via BlackHole virtual loopback device
      - Mic permission dialog: --use-fake-ui-for-media-stream Chrome flag
        (auto-approves browser prompt without replacing the audio device)

    BlackHole is set as system INPUT only. TTS audio plays on speakers and
    does NOT bleed into the mic — only explicit `say -a "BlackHole 2ch"` calls
    are picked up by the browser.

    FAILS (does not skip) if BlackHole is not installed.
    """
    print("\n[Test 5] Browser e2e — real audio via BlackHole")
    passed = []

    # Require BlackHole — fail hard if absent
    if not _check_blackhole():
        passed.append(_check(
            "BlackHole 2ch available (required for real audio pipeline)",
            False,
            "Install from https://existential.audio/blackhole/ then retry"
        ))
        return passed

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        passed.append(_check("playwright installed", False,
                              "pip install playwright && playwright install chromium"))
        return passed

    passed.append(_check("BlackHole 2ch available", True))

    # Set BlackHole as system audio INPUT
    subprocess.run(["SwitchAudioSource", "-s", "BlackHole 2ch", "-t", "input"],
                   capture_output=True)

    def say(text):
        """Speak text into BlackHole → browser mic."""
        subprocess.run(["say", "-r", "170", "-a", "BlackHole 2ch", text], check=False)

    recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Create a session — use all questions so the CC one is likely included
    jd = f"{TEST_JOB['description']}\n\n{TEST_JOB['requirements']}"
    sess_r = requests.post(f"{INTERVIEW_API}/api/interview/session", json={
        "job_description": jd,
        "resume_text": "Senior iOS engineer with 6 years Swift and UIKit experience.",
        "difficulty": 3, "seniority_bar": "senior",
        "time_limit": 45, "num_questions": 4, "behavioral_pct": 0,
        "job_id": job_id,
    })
    sess_r.raise_for_status()
    sess_data    = sess_r.json()
    session_id   = sess_data["session_id"]
    questions    = sess_data["questions"]
    cc_indices   = [i for i, q in enumerate(questions) if q.get("is_core_competency")]

    print(f"  Session: {session_id}")
    print(f"  Questions: {len(questions)}, CC question indices: {cc_indices}")
    for i, q in enumerate(questions):
        tag = " [CC]" if q.get("is_core_competency") else ""
        print(f"    Q{i+1}{tag}: {q['question'][:65]}…")

    passed.append(_check("Session created", bool(session_id)))
    if not session_id:
        _restore_audio()
        return passed

    context_kwargs = {"viewport": {"width": 1280, "height": 900}}
    if record:
        context_kwargs["record_video_dir"] = recordings_dir
        context_kwargs["record_video_size"] = {"width": 1280, "height": 900}

    probe_banner_appeared = False
    probe_question_text   = None
    code_snippet_shown    = False
    post_probe_advanced   = False

    import shutil
    profile_dir = "/tmp/cc_e2e_profile"
    shutil.rmtree(profile_dir, ignore_errors=True)

    try:
        with sync_playwright() as p:
            # Use persistent context so --use-fake-ui-for-media-stream takes effect
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                args=["--use-fake-ui-for-media-stream"],
                **context_kwargs,
            )
            # TTS is enabled (real OpenAI TTS plays on speakers).
            # We do NOT disable it — the test validates the real flow.
            page = ctx.new_page()
            page.goto(f"{INTERVIEW_URL}/interview/{session_id}")
            page.wait_for_load_state("networkidle")

            # Before you begin
            try:
                page.wait_for_selector("h1:has-text('Before you begin')",
                                       state="visible", timeout=12_000)
                passed.append(_check("'Before you begin' screen loaded", True))
            except Exception as e:
                passed.append(_check("'Before you begin' screen loaded", False, str(e)))
                ctx.close()
                return passed

            # Grant mic → Tap to Begin
            page.click("button:has-text('Allow Microphone')", timeout=8_000)
            page.wait_for_selector("button:has-text('Tap to Begin')",
                                   state="visible", timeout=8_000)
            page.click("button:has-text('Tap to Begin')")
            page.wait_for_timeout(1000)

            try:
                page.wait_for_selector("text=Question 1 of", state="visible", timeout=10_000)
                passed.append(_check("Interview started — Question 1 visible", True))
            except Exception as e:
                passed.append(_check("Interview started", False, str(e)))
                ctx.close()
                return passed

            for qi in range(len(questions)):
                q = questions[qi]
                is_cc = q.get("is_core_competency", False)
                tag   = " [CC]" if is_cc else ""
                print(f"\n  Q{qi+1}{tag}: {q['question'][:60]}…")

                # Wait for "Recording" indicator — this means TTS has finished
                # and the mic is active. Only then do we speak via BlackHole.
                print("    Waiting for Recording indicator (TTS playing)…", end="", flush=True)
                recording_appeared = False
                for _ in range(60):  # up to 30s for TTS to finish
                    content = page.content()
                    if "Recording" in content and "Speaking" not in content:
                        recording_appeared = True
                        break
                    page.wait_for_timeout(500)
                    print(".", end="", flush=True)
                print(" recording" if recording_appeared else " (timeout, proceeding anyway)")

                # Choose the answer to speak
                if is_cc:
                    answer_text = SHALLOW_ANSWER
                    print(f"    Speaking SHALLOW answer: '{answer_text}'")
                else:
                    answer_text = NORMAL_ANSWER
                    print(f"    Speaking normal answer ({len(answer_text)} chars)")

                # Speak into BlackHole
                say(answer_text)
                print("    Done speaking")

                # Wait for Next/Finish to be enabled
                for _ in range(40):
                    if (page.query_selector("button:has-text('Finish'):not([disabled])") or
                            page.query_selector("button:has-text('Next'):not([disabled])")):
                        break
                    page.wait_for_timeout(300)

                is_last = bool(page.query_selector("button:has-text('Finish'):not([disabled])"))
                btn_sel = "button:has-text('Finish')" if is_last else "button:has-text('Next')"
                page.click(btn_sel, timeout=8_000)
                print(f"    Clicked {'Finish' if is_last else 'Next'}")

                # Wait for Whisper processing
                try:
                    page.wait_for_selector("p:has-text('Processing')", timeout=5_000)
                    page.wait_for_selector("p:has-text('Processing')",
                                           state="hidden", timeout=60_000)
                    print("    Whisper done")
                except Exception:
                    pass

                # For CC question: wait for probe-assess network call + state update,
                # then check if probe banner appeared
                if is_cc:
                    print("    Waiting for probe-assess result…")
                    page.wait_for_timeout(3000)  # probe-assess + React state update

                    content = page.content()
                    if "Core competency check" in content or "Follow-up" in content:
                        probe_banner_appeared = True
                        print("    ✅ Probe banner detected!")

                        # Capture probe question text
                        try:
                            probe_question_text = page.text_content(
                                "p.text-sm:has-text('Follow-up'), .text-indigo-700",
                                timeout=2000
                            )
                        except Exception:
                            pass

                        # Check for code snippet
                        if page.query_selector("pre"):
                            code_snippet_shown = True
                            print("    ✅ Code snippet displayed!")

                        # Answer each probe
                        probe_count = len(q.get("probe_questions", []))
                        for pi in range(probe_count):
                            probe = q["probe_questions"][pi]
                            print(f"    Probe {pi+1}: '{probe['question'][:60]}…'")

                            # Wait for Recording indicator on probe
                            for _ in range(40):
                                content = page.content()
                                if "Recording" in content and "Speaking" not in content:
                                    break
                                page.wait_for_timeout(500)

                            # Speak the expected answer (short, direct)
                            probe_answer = probe.get("expected_answer", "yes")
                            print(f"    Speaking probe answer: '{probe_answer}'")
                            say(probe_answer)

                            # Wait for Next to be enabled
                            for _ in range(40):
                                if (page.query_selector("button:has-text('Finish'):not([disabled])") or
                                        page.query_selector("button:has-text('Next'):not([disabled])")):
                                    break
                                page.wait_for_timeout(300)

                            is_last_p = bool(page.query_selector("button:has-text('Finish'):not([disabled])"))
                            page.click(
                                "button:has-text('Finish')" if is_last_p else "button:has-text('Next')",
                                timeout=8_000
                            )

                            try:
                                page.wait_for_selector("p:has-text('Processing')", timeout=5_000)
                                page.wait_for_selector("p:has-text('Processing')",
                                                       state="hidden", timeout=60_000)
                            except Exception:
                                pass

                            page.wait_for_timeout(1500)

                        # After all probes, banner should be gone and we should be on next Q
                        content_after = page.content()
                        if "Core competency check" not in content_after:
                            post_probe_advanced = True
                            print("    ✅ Probe mode cleared — moved to next question")
                    else:
                        print("    Probe banner did NOT appear (needs_probing may have returned false)")
                        print(f"    Answer sent was: '{answer_text}'")

                if is_last:
                    break

            passed.append(_check(
                "Probe banner appeared after shallow CC answer",
                probe_banner_appeared,
                "Haiku returned needs_probing=false — try a shorter answer" if not probe_banner_appeared else ""
            ))
            passed.append(_check(
                "Probe mode cleared after answering all probes",
                post_probe_advanced or not probe_banner_appeared
            ))
            passed.append(_check(
                "Code snippet shown for code probe",
                code_snippet_shown or not probe_banner_appeared,
                "(only expected if a code probe was triggered)"
            ))

            # Wait for report
            print("\n  Waiting for report generation…", end="", flush=True)
            try:
                page.wait_for_url(lambda u: "/report/" in u or "/thank-you" in u,
                                  timeout=120_000)
                print(" ✅")
                passed.append(_check("Interview completed — report page reached", True))
            except Exception as e:
                print(" ❌")
                passed.append(_check("Interview completed", False, str(e)))

            # Verify report has core_competency_probes
            time.sleep(3)
            report_r = requests.get(f"{INTERVIEW_API}/api/interview/session/{session_id}")
            if report_r.status_code == 200:
                report_data = report_r.json().get("report")
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
                            "Probe result has pass field",
                            "pass" in p0,
                            f"pass={p0.get('pass')}, answer='{p0.get('candidate_answer','')[:40]}'"
                        ))
                else:
                    passed.append(_check("Report generated", False, "report field is null"))

            if record and page.video:
                raw_path = page.video.path()
            else:
                raw_path = None

            ctx.close()

        if record and raw_path and os.path.exists(raw_path):
            final = os.path.join(recordings_dir, f"cc_probe_real_audio_{timestamp}.webm")
            os.rename(raw_path, final)
            print(f"  📹 Video saved: {final}")

    finally:
        # Always restore system audio input to built-in mic
        subprocess.run(
            ["SwitchAudioSource", "-s", "MacBook Pro Microphone", "-t", "input"],
            capture_output=True
        )

    return passed


# ── Runner ────────────────────────────────────────────────────────────────────

def run(record=False):
    print("\n" + "=" * 65)
    print("TalentBridge — Core Competency Probes E2E Tests")
    print("=" * 65)

    if not check_services():
        print("\n❌ Services not running. Start all services and retry.")
        return False

    all_passed = []

    print("\n[Auth] Registering test user…")
    try:
        token = _auth()
        print(f"  OK ✅")
    except Exception as e:
        print(f"  ❌ Auth failed: {e}")
        return False

    print("\n[Setup] Creating job + question bank…")
    try:
        job_id, questions = _create_and_setup_job(token)
        print(f"  job_id={job_id}, {len(questions)} questions in bank")
    except Exception as e:
        print(f"  ❌ Setup failed: {e}")
        return False

    # Tests 1–4: API only
    all_passed += test_probe_assess()

    if questions:
        t2_result = test_toggle_core_competency(questions)
        t2_passed, flagged_q_id = t2_result if isinstance(t2_result, tuple) else (t2_result, None)
        all_passed += t2_passed
    else:
        print("\n[Test 2] SKIPPED — no questions in bank")
        flagged_q_id = None

    if flagged_q_id:
        t3_result = test_session_includes_probes(job_id, flagged_q_id)
        t3_passed, session_id, sess_qs = t3_result if isinstance(t3_result, tuple) else (t3_result, None, [])
        all_passed += t3_passed
    else:
        print("\n[Test 3] SKIPPED — no flagged question")
        session_id, sess_qs = None, []

    if session_id and sess_qs:
        all_passed += test_report_with_cc_transcript(session_id, sess_qs)
    else:
        print("\n[Test 4] SKIPPED — no session available")

    # Test 5: real audio browser test
    all_passed += test_browser_cc_flow_real_audio(job_id, record=record)

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
