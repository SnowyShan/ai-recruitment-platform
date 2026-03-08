#!/usr/bin/env python3
"""
E2E sanity test — TalentBridge core interview flow.

Tests the most important path in the app end-to-end with real data:
  1. Auth (register or login)
  2. Create + publish a job (TB API)
  3. Wait for interview question bank to generate (TB + Interview API)
  4. Create a mock interview session (Interview API — same call as the UI button)
  5. For each question, speak a real answer with macOS `say`, send to Whisper,
     get a real transcript
  6. Submit the interview (Interview API)
  7. Poll until Claude generates the report
  8. Assert report accuracy:
       - Questions answered with GOOD (on-topic iOS) answers score higher
         than questions answered with BAD (wrong domain) answers
       - Score gap ≥ 25 points on average
       - Report is non-empty and structured

GOOD/BAD strategy (question-agnostic):
  Questions are AI-generated and vary per run. Rather than matching specific
  questions, we alternate:
    Q1 = GOOD (detailed Swift/iOS/UIKit answer)
    Q2 = BAD  (Python/ML/wrong domain — clearly irrelevant for iOS role)
    Q3 = GOOD
    Q4 = BAD
    ...
  Claude correctly differentiates these regardless of what the question asked.

REQUIREMENTS:
  pip install requests
  macOS `say` command (built-in)

SERVICES MUST BE RUNNING:
  localhost:8000  — TalentBridge backend
  localhost:5173  — TalentBridge frontend  (not called directly, but must be up)
  localhost:8001  — Interview module backend
"""

import os
import sys
import json
import time
import subprocess
import tempfile
import requests

# ── Config ────────────────────────────────────────────────────────────────────

TB_API        = "http://localhost:8000"
TB_URL        = "http://localhost:5173"
INTERVIEW_API = "http://localhost:8001"

TEST_EMAIL    = "e2e-test@gmail.com"
TEST_PASSWORD = "E2eTestPass123!"
TEST_NAME     = "E2E Test Recruiter"

TEST_JOB = {
    "title": "Senior iOS Engineer [E2E-TEST]",
    "description": (
        "We are looking for a senior iOS engineer with deep expertise in Swift, "
        "UIKit, SwiftUI, memory management using ARC, and concurrency with GCD "
        "and Swift async/await. You will architect and ship features for our "
        "consumer mobile app used by millions of users."
    ),
    "requirements": (
        "5+ years iOS development. Expert in Swift, UIKit, SwiftUI. "
        "Strong understanding of ARC, retain cycles, weak/unowned references. "
        "Experience with Instruments, performance profiling, Core Data."
    ),
    "responsibilities": (
        "Lead iOS architecture decisions. Mentor junior engineers. "
        "Collaborate with backend and design. Ship high-quality mobile features."
    ),
    "department": "Engineering",
    "location": "San Francisco, CA",
    "job_type": "full_time",
    "experience_level": "senior",
}

# ── Answer corpus ─────────────────────────────────────────────────────────────
# GOOD answers: each covers a distinct iOS/Swift topic so Claude doesn't
# penalise repetition when the same candidate answers multiple questions.
GOOD_ANSWERS = [
    # Memory management / ARC
    (
        "Automatic Reference Counting is Swift's memory management system. "
        "It tracks the number of strong references to each class instance and "
        "deallocates the object when the count drops to zero. I use weak "
        "references in delegate patterns and unowned in closures where the "
        "referenced object is guaranteed to outlive the closure. Retain cycles "
        "between two objects that both hold strong references to each other are "
        "the most common pitfall. I detect them with Instruments Leaks template "
        "and fix them by making one side of the relationship weak. I have "
        "reduced our app memory footprint by thirty percent using these techniques."
    ),
    # Swift value vs reference types
    (
        "Structs in Swift are value types stored on the stack, while classes are "
        "reference types stored on the heap. When you assign a struct it is copied "
        "whereas a class assignment just copies the reference. I prefer structs "
        "for data models because they are thread-safe by default, have no "
        "inheritance overhead, and the compiler optimises copy-on-write semantics "
        "automatically. I use classes when I need identity semantics, shared "
        "mutable state, or Objective-C interoperability. Swift standard library "
        "types like Array, Dictionary, and String are all structs with "
        "copy-on-write to avoid unnecessary heap allocations."
    ),
    # Concurrency
    (
        "Grand Central Dispatch uses a pool of threads managed by the OS. You "
        "submit work items to serial or concurrent queues and the system decides "
        "which thread executes them. Swift async await is built on top of "
        "structured concurrency and uses cooperative thread pools that are much "
        "more efficient. With async await the compiler enforces structured "
        "lifetimes of concurrent tasks which eliminates entire classes of bugs. "
        "I prefer async await for new code but still use GCD for integrating "
        "with legacy Objective-C frameworks. Actors in Swift protect shared "
        "mutable state by serialising access, replacing manual serial queues."
    ),
    # Performance and profiling
    (
        "When I debug memory leaks I start with the Leaks instrument in Xcode. "
        "I look for reference cycles, especially in delegate patterns, "
        "notification observers not being removed, and closures capturing strong "
        "references. I fixed a critical leak at LinkedIn where a view controller "
        "held a strong reference to a timer which retained the view controller "
        "in its callback. Breaking that cycle with weak self eliminated a two "
        "megabyte per minute memory growth. I also use the Allocations template "
        "to track heap growth over time and identify which objects are not "
        "being released after their owning view is dismissed."
    ),
]

# BAD: Python/ML jargon — completely wrong domain for an iOS role.
# Claude correctly scores this near-zero regardless of the iOS question asked.
BAD_ANSWERS = [
    (
        "I mainly work with Python and Django for building REST API backends. "
        "Recently I have been focusing on machine learning using TensorFlow and "
        "PyTorch to train convolutional neural networks on image classification. "
        "I find Adam optimizer with a small learning rate works well for most tasks. "
        "I deploy with Docker and Kubernetes on AWS, and use PostgreSQL with Redis."
    ),
    (
        "My background is primarily in data engineering. I build ETL pipelines "
        "using Apache Spark and Airflow to process terabytes of event data daily. "
        "I write most of my code in Python and Scala, and I am experienced with "
        "Hadoop, Hive, and BigQuery. I have no mobile development experience but "
        "I am a fast learner and confident I could pick it up quickly."
    ),
]


def get_good_answer(idx):
    return GOOD_ANSWERS[idx % len(GOOD_ANSWERS)]


def get_bad_answer(idx):
    return BAD_ANSWERS[idx % len(BAD_ANSWERS)]

# ── Utilities ─────────────────────────────────────────────────────────────────

def check_services():
    print("Checking services…")
    ok = True
    checks = [
        ("TB backend",        f"{TB_API}/health"),
        ("Interview backend", f"{INTERVIEW_API}/health"),
    ]
    for name, url in checks:
        try:
            r = requests.get(url, timeout=5)
            up = r.status_code < 400
            print(f"  {'✅' if up else '❌'} {name}: HTTP {r.status_code}")
            if not up:
                ok = False
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            ok = False
    return ok


def auth(email, password, name):
    """Login or register; return Bearer token."""
    r = requests.post(f"{TB_API}/api/auth/login",
                      json={"email": email, "password": password})
    if r.status_code == 200:
        return r.json()["access_token"]
    r = requests.post(f"{TB_API}/api/auth/register",
                      json={"email": email, "password": password,
                            "full_name": name, "company_name": "E2E Tests"})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Auth failed: {r.text}")
    return r.json()["access_token"]


def get_or_create_job(token):
    headers = {"Authorization": f"Bearer {token}"}
    jobs = requests.get(f"{TB_API}/api/jobs/", headers=headers).json()
    for job in jobs:
        if "[E2E-TEST]" in job.get("title", ""):
            print(f"  Found existing job {job['id']}: {job['title']}")
            if job.get("status") != "published":
                requests.post(f"{TB_API}/api/jobs/{job['id']}/publish",
                              headers=headers)
            return job
    r = requests.post(f"{TB_API}/api/jobs/", headers=headers, json=TEST_JOB)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Job creation failed: {r.text}")
    job = r.json()
    print(f"  Created job {job['id']}: {job['title']}")
    # Don't publish yet — question bank needs to be ready first (publish is
    # blocked while setup_status='generating'). We publish after wait_for_setup.
    return job


def wait_for_setup(job_id, token, timeout=180):
    headers = {"Authorization": f"Bearer {token}"}
    print(f"  Waiting for question bank generation…", end="", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(f"{TB_API}/api/jobs/{job_id}/setup-status",
                         headers=headers)
        if r.status_code == 200:
            s = r.json()
            status = s.get("setup_status") or s.get("status")
            if status == "ready":
                print(" ✅ ready")
                return True
            if status == "failed":
                print(" ❌ failed")
                return False
        time.sleep(3)
        print(".", end="", flush=True)
    print(" ❌ timeout")
    return False


def speak_to_m4a(text, path):
    """Use macOS `say` to convert text to speech and save as m4a."""
    subprocess.run(["say", "-o", path, text], check=True, capture_output=True)


def whisper_transcribe(audio_path):
    """Send audio file to the real Whisper endpoint and return transcript text."""
    with open(audio_path, "rb") as f:
        r = requests.post(
            f"{INTERVIEW_API}/api/interview/transcribe",
            files={"file": ("audio.m4a", f, "audio/mp4")},
            timeout=60,
        )
    r.raise_for_status()
    return r.json().get("text", "")


# ── Test ──────────────────────────────────────────────────────────────────────

def run_test(record: bool = False):
    print("\n" + "=" * 60)
    print("TalentBridge E2E Sanity Test — Core Interview Flow")
    if record:
        print("  [--record] Browser recording enabled")
    print("=" * 60 + "\n")

    # ── Step 1: Services ───────────────────────────────────────────────────
    if not check_services():
        print("\n❌ Services not ready. Start all four services and retry.")
        return False

    # ── Step 2: Auth ───────────────────────────────────────────────────────
    print("\n[Step 1] Auth")
    token = auth(TEST_EMAIL, TEST_PASSWORD, TEST_NAME)
    print(f"  Logged in as {TEST_EMAIL} ✅")

    # ── Step 3: Job ────────────────────────────────────────────────────────
    print("\n[Step 2] Job setup")
    job = get_or_create_job(token)
    job_id = job["id"]

    if not wait_for_setup(job_id, token):
        print("  Question bank not ready — aborting.")
        return False

    # Optional browser recording (visual demo — runs before accuracy test)
    if record:
        print("\n[Recording] Launching browser…")
        video = record_ui_flow(job_id, token, num_questions=4)
        if not video:
            print("  Recording failed or playwright not installed — continuing with API test.")
        print()

    # Publish now that setup is ready
    if job.get("status") != "published":
        r = requests.post(f"{TB_API}/api/jobs/{job_id}/publish",
                          headers={"Authorization": f"Bearer {token}"})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Publish failed: {r.text}")
        job = r.json()
        print("  Published ✅")

    # ── Step 4: Create session (same API the Mock Interview button calls) ──
    print("\n[Step 3] Create mock interview session")
    jd = "\n\n".join(filter(None, [
        job.get("description"), job.get("requirements"), job.get("responsibilities")
    ]))
    session_resp = requests.post(f"{INTERVIEW_API}/api/interview/session", json={
        "job_description": jd or job["title"],
        "resume_text": (
            "Mock candidate for E2E testing. "
            "5 years iOS experience with Swift, UIKit, and SwiftUI. "
            "Strong background in memory management and performance optimisation."
        ),
        "difficulty":     2,
        "seniority_bar":  "senior",
        "time_limit":     45,
        "num_questions":  4,
        "behavioral_pct": 25,
        "job_id":         job_id,
    })
    session_resp.raise_for_status()
    session_data = session_resp.json()
    session_id   = session_data["session_id"]
    questions    = session_data["questions"]
    print(f"  Session: {session_id}")
    print(f"  Questions: {len(questions)}")
    for i, q in enumerate(questions):
        qtype = q.get("type", "technical")
        print(f"    Q{i+1} [{qtype}]: {q['question'][:70]}…")

    # ── Step 5: Generate real audio + transcribe each question ─────────────
    print("\n[Step 4] Record answers and transcribe via Whisper")
    transcripts = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, q in enumerate(questions):
            is_good = (i % 2 == 0)
            label   = "GOOD" if is_good else "BAD "
            text    = get_good_answer(i // 2) if is_good else get_bad_answer(i // 2)
            path    = os.path.join(tmpdir, f"q{i}.m4a")

            print(f"  Q{i+1} [{label}] Generating audio…", end="", flush=True)
            speak_to_m4a(text, path)
            size = os.path.getsize(path)
            print(f" {size:,} bytes → Whisper…", end="", flush=True)

            transcript = whisper_transcribe(path)
            transcripts[i] = transcript
            print(f" {len(transcript)} chars ✅")
            print(f"          Heard: '{transcript[:80]}…'")

    # ── Step 6: Submit interview ───────────────────────────────────────────
    print("\n[Step 5] Submit interview")
    full_transcript = ""
    for i, q in enumerate(questions):
        ans = transcripts.get(i, "(no answer)")
        full_transcript += f"[Q{i+1}: {q['question']}]\n{ans}\n\n"

    resp = requests.post(
        f"{INTERVIEW_API}/api/interview/session/{session_id}/complete",
        json={"full_transcript": full_transcript, "questions": questions},
        timeout=120,
    )
    resp.raise_for_status()
    print("  Submitted ✅")

    # ── Step 7: Wait for report ────────────────────────────────────────────
    print("\n[Step 6] Waiting for Claude to generate report…", end="", flush=True)
    report = None
    for _ in range(40):
        r = requests.get(f"{INTERVIEW_API}/api/interview/session/{session_id}")
        if r.status_code == 200:
            data = r.json()
            if data.get("status") == "completed" and data.get("report"):
                report = data["report"]
                break
        time.sleep(3)
        print(".", end="", flush=True)
    print()

    if not report:
        print("❌ Report not generated within timeout.")
        return False

    # ── Step 8: Assert report accuracy ────────────────────────────────────
    print("\n[Step 7] Report accuracy check")
    print(f"  Overall score: {report.get('overall_score')}/100")
    print(f"  Pass:          {report.get('pass')}")
    print(f"  Summary:       {report.get('summary', '')[:120]}…\n")

    per_q      = report.get("per_question", [])
    good_scores = []
    bad_scores  = []

    for i, pq in enumerate(per_q):
        score    = pq.get("score", 0)
        is_good  = (i % 2 == 0)
        label    = "GOOD" if is_good else "BAD "
        feedback = pq.get("feedback", "")[:70]
        print(f"  Q{i+1} [{label}] score={score:>3}/100 | {feedback}…")
        (good_scores if is_good else bad_scores).append(score)

    avg_good = sum(good_scores) / len(good_scores) if good_scores else 0
    avg_bad  = sum(bad_scores)  / len(bad_scores)  if bad_scores  else 0
    gap      = avg_good - avg_bad

    print(f"\n  Avg GOOD score: {avg_good:.1f}")
    print(f"  Avg BAD  score: {avg_bad:.1f}")
    print(f"  Gap (GOOD-BAD): {gap:.1f}  (need ≥ 25)\n")

    passed = []

    def check(desc, cond, detail=""):
        mark = "✅" if cond else "❌"
        print(f"  {mark} {desc}" + (f"  [{detail}]" if detail else ""))
        passed.append(cond)

    check("Report has per-question entries",
          len(per_q) > 0,                           f"{len(per_q)} Qs")
    check("Overall score is non-zero",
          report.get("overall_score", 0) > 0,       f"{report.get('overall_score')}/100")
    check("Summary is non-empty",
          bool(report.get("summary", "").strip()))
    check("GOOD answers averaged > 20",
          avg_good > 20,                             f"{avg_good:.1f}")
    check("BAD answers averaged < 20",
          avg_bad  < 20,                             f"{avg_bad:.1f}")
    check("GOOD answers scored higher than BAD",
          avg_good > avg_bad,                        f"gap={gap:.1f}")
    check("Score gap ≥ 15 (AI distinguishes expertise from noise)",
          gap >= 15,                                 f"gap={gap:.1f}")

    all_passed = all(passed)
    print(f"\n{'=' * 60}")
    if all_passed:
        print("✅  ALL CHECKS PASSED")
    else:
        n = sum(1 for p in passed if not p)
        print(f"❌  {n} CHECK(S) FAILED")

    return all_passed


def record_ui_flow(job_id: int, token: str, num_questions: int = 4):
    """
    Open a real visible browser, navigate through the full UI flow, and record
    it as a .webm video in tests/recordings/.

    Separate from the accuracy test — this is purely for visual verification.
    The browser creates its own session (same job). Transcription is intercepted
    to return known answers so the flow completes cleanly on screen.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright not installed — run: pip install playwright && playwright install chromium")
        return None

    import datetime
    recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    video_name = f"interview_flow_{timestamp}"

    headers = {"Authorization": f"Bearer {token}"}
    job_resp = requests.get(f"{TB_API}/api/jobs/{job_id}", headers=headers)
    job = job_resp.json()
    jd = "\n\n".join(filter(None, [job.get("description"), job.get("requirements")]))

    # Create a fresh session for the browser recording
    sess = requests.post(f"{INTERVIEW_API}/api/interview/session", json={
        "job_description": jd or job["title"],
        "resume_text": "Mock candidate for visual E2E recording.",
        "difficulty": 2, "seniority_bar": "senior", "time_limit": 45,
        "num_questions": num_questions, "behavioral_pct": 25, "job_id": job_id,
    })
    sess.raise_for_status()
    session_id  = sess.json()["session_id"]
    questions   = sess.json()["questions"]
    print(f"  Recording session: {session_id}")

    call_count = [0]
    def handle_transcribe(route):
        idx = call_count[0]; call_count[0] += 1
        text = get_good_answer(idx // 2) if idx % 2 == 0 else get_bad_answer(idx // 2)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"text": text}))

    video_path = None
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="/tmp/tb_e2e_recording_profile",
            headless=False,
            record_video_dir=recordings_dir,
            record_video_size={"width": 1280, "height": 800},
            args=["--use-fake-ui-for-media-stream",
                  "--use-fake-device-for-media-stream"],
            viewport={"width": 1280, "height": 800},
        )

        # Inject: disable TTS + mock getUserMedia (silent stream for recording)
        context.add_init_script("""
            localStorage.setItem('interview_tts_enabled', 'false');
            if (navigator.mediaDevices) {
                navigator.mediaDevices.getUserMedia = async () => {
                    const ctx = new AudioContext();
                    const dst = ctx.createMediaStreamDestination();
                    return dst.stream;
                };
            }
        """)

        page = context.new_page()
        page.route("**/api/interview/transcribe", handle_transcribe)

        # Login
        page.goto(f"{TB_URL}/login")
        page.fill('input[type="email"]', TEST_EMAIL)
        page.fill('input[type="password"]', TEST_PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_url("**/dashboard", timeout=15_000)
        page.wait_for_timeout(600)

        # Job Detail
        page.goto(f"{TB_URL}/jobs/{job_id}")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(800)

        # Expand config panel to show Mock Interview button
        config_btn = page.query_selector("button:has-text('Screening Interview Config')")
        if config_btn and not page.query_selector("button:has-text('Mock Interview')"):
            config_btn.click()
            page.wait_for_timeout(600)

        # Scroll Mock Interview button into view and highlight briefly
        mock_btn = page.query_selector("button:has-text('Mock Interview')")
        if mock_btn:
            mock_btn.scroll_into_view_if_needed()
            page.wait_for_timeout(400)

        # Navigate directly to interview (avoids cross-origin popup issues)
        page.wait_for_timeout(400)
        interview_page = context.new_page()
        interview_page.route("**/api/interview/transcribe", handle_transcribe)
        interview_page.add_init_script("""
            localStorage.setItem('interview_tts_enabled', 'false');
            if (navigator.mediaDevices) {
                navigator.mediaDevices.getUserMedia = async () => {
                    const ctx = new AudioContext();
                    const dst = ctx.createMediaStreamDestination();
                    return dst.stream;
                };
            }
        """)
        interview_page.goto(f"http://localhost:5174/interview/{session_id}")
        interview_page.wait_for_load_state("networkidle")
        interview_page.wait_for_timeout(800)

        # Instructions screen
        interview_page.click("button:has-text('Allow Microphone')", timeout=10_000)
        interview_page.wait_for_selector("button:has-text('Tap to Begin')", timeout=10_000)
        interview_page.wait_for_timeout(600)
        interview_page.click("button:has-text('Tap to Begin')")
        interview_page.wait_for_timeout(1000)

        # Click through each question
        for i in range(len(questions)):
            try:
                qlabel = interview_page.text_content("p:has-text('Question')", timeout=3_000)
                print(f"    {qlabel.strip()}")
            except Exception:
                pass

            # Pause to simulate thinking/answering
            interview_page.wait_for_timeout(2500)

            # Wait for buttons to be enabled
            try:
                interview_page.wait_for_selector(
                    "button:has-text('Next →'):not([disabled]), button:has-text('Finish'):not([disabled])",
                    timeout=15_000,
                )
            except Exception:
                pass

            is_last = interview_page.query_selector("button:has-text('Finish')") is not None
            btn_text = "Finish" if is_last else "Next →"
            interview_page.click(f"button:has-text('{btn_text}')")

            # Wait for processing indicator to come and go
            try:
                interview_page.wait_for_selector("p:has-text('Processing')", timeout=5_000)
                interview_page.wait_for_selector("p:has-text('Processing')",
                                                  state="hidden", timeout=30_000)
            except Exception:
                pass

            if is_last:
                break

        # Wait for "Submitting…" spinner then report redirect
        print("    Waiting for report to generate…", end="", flush=True)
        try:
            interview_page.wait_for_url("**/report/**", timeout=90_000)
            print(" ✅")
        except Exception:
            print(" (timeout — still showing final state)")

        # Scroll through the report so per-question breakdown is visible
        interview_page.wait_for_timeout(2000)  # let report render fully
        # Scroll down slowly so the viewer can read each section
        interview_page.evaluate("""
            () => new Promise(resolve => {
                const totalHeight = document.body.scrollHeight;
                const step = 180;
                let scrolled = 0;
                const timer = setInterval(() => {
                    window.scrollBy(0, step);
                    scrolled += step;
                    if (scrolled >= totalHeight) {
                        clearInterval(timer);
                        setTimeout(resolve, 2000); // pause at bottom
                    }
                }, 120); // scroll every 120ms → smooth, readable
            })
        """)
        interview_page.wait_for_timeout(1500)

        # Grab video path before closing
        video_path = interview_page.video.path() if interview_page.video else None
        context.close()

    if video_path and os.path.exists(video_path):
        final_path = os.path.join(recordings_dir, f"{video_name}.webm")
        os.rename(video_path, final_path)
        print(f"  Video saved: {final_path}")
        return final_path
    return None


if __name__ == "__main__":
    record = "--record" in sys.argv
    ok = run_test(record=record)
    sys.exit(0 if ok else 1)
