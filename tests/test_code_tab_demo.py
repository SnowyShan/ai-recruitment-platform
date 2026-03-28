"""
Task 11 Phase 1 demo — Code Editor Tab
Records a video showing the coding tab in Interview.jsx.
"""

import requests, json, time, subprocess, os, sys
from datetime import datetime
from playwright.sync_api import sync_playwright, expect

BASE_IM = "http://localhost:8001"
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

CODE_SOLUTION = """\
def can_see_ocean(heights):
    # A building can see the ocean if no taller building is to its right.
    # Traverse right-to-left tracking the max height seen so far.
    result = []
    max_right = 0

    for i in range(len(heights) - 1, -1, -1):
        if heights[i] > max_right:
            result.append(i)
            max_right = heights[i]

    return sorted(result)  # left-to-right order

# Example:
# heights = [3, 1, 4, 2, 5]
# Only building at index 4 (h=5) sees ocean — all others blocked
print(can_see_ocean([3, 1, 4, 2, 5]))   # [4]
print(can_see_ocean([4, 3, 2, 1]))       # [0,1,2,3] — all descending, all see ocean

# Edge cases:
# Empty list → []
# Single building → [0]
# All same height → only rightmost sees ocean
"""


def create_session():
    resp = requests.post(f"{BASE_IM}/api/interview/session", json={
        "job_id": 15,
        "candidate_name": "Alex Rivera",
        "candidate_email": "alex@candidate.com",
        "resume_text": "4 years Python/JS. Built data pipelines and REST APIs at TechCorp.",
        "job_description": "Senior Software Engineer",
        "difficulty_level": 2,
        "seniority_bar": "mid",
        "max_duration_minutes": 20,
        "verify_coding_ability": True,
        "num_behavioral_questions": 1
    })
    data = resp.json()
    session_id = data["session_id"]
    questions = data["questions"]
    coding_idx = next((i for i, q in enumerate(questions) if q.get("type") == "coding"), None)
    print(f"Session: {session_id}")
    print(f"Questions: {len(questions)} total, coding at index {coding_idx}")
    if coding_idx is not None:
        print(f"Coding Q: {questions[coding_idx]['question'][:120]}...")
    return session_id, questions, coding_idx


def run_demo(session_id, questions, coding_idx):
    interview_url = f"http://localhost:5174/interview/{session_id}"
    report_url = f"http://localhost:5174/report/{session_id}"
    num_questions = len(questions)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--use-fake-ui-for-media-stream",
                "--use-fake-device-for-media-stream",
                "--no-sandbox",
            ]
        )
        context = browser.new_context(
            record_video_dir=RECORDINGS_DIR,
            record_video_size={"width": 1280, "height": 800},
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # --- Step 1: Load interview ---
        print(f"\nOpening {interview_url}")
        page.goto(interview_url, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # --- Step 2: Click "Allow Microphone & Continue" ---
        print("Waiting for 'Allow Microphone & Continue'...")
        page.wait_for_selector("text=Allow Microphone & Continue", timeout=10000)
        page.click("text=Allow Microphone & Continue")
        page.wait_for_timeout(1500)
        print("Clicked 'Allow Microphone & Continue' ✅")

        # --- Step 3: Wait for "Tap to Begin →" then click it ---
        print("Waiting for 'Tap to Begin'...")
        page.wait_for_selector("text=Tap to Begin", timeout=10000)
        page.wait_for_timeout(500)
        page.click("text=Tap to Begin")
        print("Clicked 'Tap to Begin' ✅")
        page.wait_for_timeout(3000)

        # --- Step 4: Walk through questions ---
        for i in range(num_questions):
            q_type = questions[i].get("type", "technical")
            print(f"\n--- Question {i+1}/{num_questions} (type={q_type}) ---")

            if i == coding_idx:
                # Wait a bit for TTS to play question audio
                page.wait_for_timeout(4000)

                print("Coding question — looking for Code tab...")
                # Wait for the tab bar to appear
                try:
                    page.wait_for_selector("text=💻 Code", timeout=8000)
                    page.click("text=💻 Code")
                    print("  Clicked '💻 Code' tab ✅")
                    page.wait_for_timeout(800)
                except Exception as e:
                    print(f"  Code tab not found: {e}")
                    # Take debug screenshot
                    page.screenshot(path="/tmp/debug_code_tab.png")
                    # Try alternative
                    try:
                        page.click("button:has-text('Code')", timeout=3000)
                        print("  Clicked via button:has-text('Code') ✅")
                    except:
                        print("  Could not find code tab at all — checking HTML")
                        content = page.content()
                        if "verifyCoding" in content or "code-tab" in content or "💻" in content:
                            print("  Tab markup IS in page")
                        else:
                            print("  Tab markup NOT in page — verifyCoding may be false")

                # Type solution in textarea
                try:
                    page.wait_for_selector("textarea", timeout=5000)
                    ta = page.locator("textarea").first
                    ta.click()
                    page.wait_for_timeout(300)
                    ta.fill(CODE_SOLUTION)
                    print(f"  Typed solution ({len(CODE_SOLUTION)} chars) ✅")
                    page.wait_for_timeout(4000)  # Pause so viewer can read code
                except Exception as e:
                    print(f"  Textarea error: {e}")

            else:
                # Non-coding question: wait briefly for TTS then click Next
                page.wait_for_timeout(2000)

            # Wait for Next/Finish button to be ENABLED (Whisper may still be processing)
            # Last question shows "Finish", others show "Next →"
            advanced = False
            for btn_label in ["Next", "Finish"]:
                try:
                    page.wait_for_selector(
                        f"button:has-text('{btn_label}'):not([disabled])",
                        timeout=30000
                    )
                    page.click(f"button:has-text('{btn_label}')")
                    print(f"  Clicked '{btn_label}' ✅")
                    page.wait_for_timeout(1500)
                    advanced = True
                    break
                except:
                    pass
            if not advanced:
                print("  No advance button found (timeout)")

        # --- Step 5: Poll API until session is completed (report generated) ---
        print("\nPolling API until report is ready...")
        import time as _time
        for attempt in range(30):
            _time.sleep(3)
            r = requests.get(f"{BASE_IM}/api/interview/session/{session_id}")
            status = r.json().get("status")
            has_report = bool(r.json().get("report"))
            print(f"  t={attempt*3+3}s status={status} report={has_report}")
            if status == "completed" and has_report:
                print("  Report ready ✅")
                break
        else:
            print("  Timed out waiting for report")

        # --- Step 6: Navigate to report ---
        print(f"\nNavigating to report: {report_url}")
        page.goto(report_url, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # Scroll slowly through the report summary
        print("Scrolling through report summary...")
        for _ in range(4):
            page.evaluate("window.scrollBy(0, 250)")
            page.wait_for_timeout(800)

        # Find and click the last question card (coding question Q9) to expand it
        print("Expanding coding question (Q9) in report...")
        try:
            q_buttons = page.locator(".card button").all()
            print(f"  Found {len(q_buttons)} question cards")
            if q_buttons:
                last_btn = q_buttons[-1]
                last_btn.scroll_into_view_if_needed()
                page.wait_for_timeout(1000)
                last_btn.click()
                page.wait_for_timeout(1500)
                print("  Expanded Q9 ✅")

                # Wait for code block to appear
                page.wait_for_selector("pre", timeout=10000)
                page.wait_for_timeout(500)
                pre = page.locator("pre").first
                pre.scroll_into_view_if_needed()
                page.wait_for_timeout(1500)
                print("  Code block visible ✅")

                # Scroll down slowly to reveal code + analysis
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, 200)")
                    page.wait_for_timeout(800)
        except Exception as e:
            print(f"  Report expand error: {e}")

        page.wait_for_timeout(3000)

        page.wait_for_timeout(3000)
        video_path = page.video.path() if page.video else None
        context.close()
        browser.close()
        return video_path


def convert_to_mp4(webm_path, out_path):
    result = subprocess.run([
        "ffmpeg", "-y", "-i", webm_path,
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-c:a", "aac", out_path
    ], capture_output=True, text=True)
    if result.returncode == 0:
        return out_path
    print("ffmpeg stderr:", result.stderr[-300:])
    return None


if __name__ == "__main__":
    session_id, questions, coding_idx = create_session()
    video_path = run_demo(session_id, questions, coding_idx)

    if video_path and os.path.exists(video_path):
        out = "/Users/openclaw/Documents/projects/ai-recruitment-platform/task11_code_tab_demo.mp4"
        mp4 = convert_to_mp4(video_path, out)
        if mp4:
            size_mb = os.path.getsize(mp4) / 1024 / 1024
            print(f"\n✅ Video saved: {mp4} ({size_mb:.1f} MB)")
            subprocess.run(["openclaw", "system", "event",
                "--text", f"Done: Task 11 code tab demo ready ({size_mb:.1f}MB)",
                "--mode", "now"])
        else:
            print(f"Conversion failed. Raw webm: {video_path}")
    else:
        print("No video produced")
