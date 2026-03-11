"""
Task 11 Phase 2 E2E test — Excalidraw Draw tab
Verifies: draw tab renders, drawing is submitted, report shows image + analysis.
"""

import requests, json, time, os
from playwright.sync_api import sync_playwright, expect

BASE_IM = "http://localhost:8001"
FRONTEND = "http://localhost:5174"
RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)


def create_session():
    """Create an interview session via API."""
    resp = requests.post(f"{BASE_IM}/api/interview/session", json={
        "job_id": 15,
        "resume_text": "4 years Python/JS. Built data pipelines and REST APIs at TechCorp.",
        "job_description": "Senior Software Engineer",
        "difficulty": 2,
        "seniority_bar": "mid",
        "time_limit": 20,
        "verify_coding_ability": False,
        "behavioral_pct": 20,
        "num_questions": 3,
    })
    resp.raise_for_status()
    data = resp.json()
    return data["session_id"], data["questions"]


def test_draw_tab_e2e():
    session_id, questions = create_session()
    print(f"Session: {session_id}, {len(questions)} questions")

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

        # ── Step 1: Load interview ──
        interview_url = f"{FRONTEND}/interview/{session_id}"
        print(f"Opening {interview_url}")
        page.goto(interview_url, wait_until="networkidle")
        page.wait_for_timeout(2000)

        # ── Step 2: Grant mic + start ──
        page.wait_for_selector("text=Allow Microphone & Continue", timeout=10000)
        page.click("text=Allow Microphone & Continue")
        page.wait_for_timeout(1500)
        page.wait_for_selector("text=Tap to Begin", timeout=10000)
        page.click("text=Tap to Begin")
        print("Interview started")
        page.wait_for_timeout(3000)

        # ── Step 3: On Q1, answer voice (wait for TTS) then switch to Draw tab ──
        print("Q1: Switching to Draw tab...")
        page.wait_for_selector("text=🎨 Draw", timeout=8000)
        page.click("text=🎨 Draw")
        page.wait_for_timeout(2000)

        # ── Step 4: Draw something on the Excalidraw canvas ──
        # Inject elements via the exposed __excalidrawAPI
        print("Injecting drawing elements via Excalidraw API...")
        page.wait_for_function("() => !!window.__excalidrawAPI", timeout=10000)
        page.evaluate("""() => {
            const api = window.__excalidrawAPI;
            if (!api) throw new Error('Excalidraw API not available');
            api.updateScene({
                elements: [
                    {
                        type: "rectangle",
                        id: "test-rect-1",
                        x: 100, y: 100, width: 200, height: 120,
                        strokeColor: "#1e1e1e",
                        backgroundColor: "#a5d8ff",
                        fillStyle: "solid",
                        strokeWidth: 2,
                        roughness: 1,
                        opacity: 100,
                        angle: 0,
                        groupIds: [],
                        frameId: null,
                        index: "a0",
                        roundness: { type: 3 },
                        seed: 1,
                        version: 1,
                        versionNonce: 1,
                        isDeleted: false,
                        boundElements: null,
                        updated: Date.now(),
                        link: null,
                        locked: false,
                    },
                    {
                        type: "text",
                        id: "test-text-1",
                        x: 130, y: 140, width: 140, height: 25,
                        text: "System Design",
                        fontSize: 20,
                        fontFamily: 5,
                        textAlign: "center",
                        verticalAlign: "middle",
                        strokeColor: "#1e1e1e",
                        backgroundColor: "transparent",
                        fillStyle: "solid",
                        strokeWidth: 1,
                        roughness: 1,
                        opacity: 100,
                        angle: 0,
                        groupIds: [],
                        frameId: null,
                        index: "a1",
                        roundness: null,
                        seed: 2,
                        version: 1,
                        versionNonce: 2,
                        isDeleted: false,
                        boundElements: null,
                        updated: Date.now(),
                        link: null,
                        locked: false,
                        containerId: null,
                        originalText: "System Design",
                        autoResize: true,
                        lineHeight: 1.25,
                    },
                    {
                        type: "arrow",
                        id: "test-arrow-1",
                        x: 300, y: 160, width: 100, height: 0,
                        points: [[0, 0], [100, 0]],
                        strokeColor: "#1e1e1e",
                        backgroundColor: "transparent",
                        fillStyle: "solid",
                        strokeWidth: 2,
                        roughness: 1,
                        opacity: 100,
                        angle: 0,
                        groupIds: [],
                        frameId: null,
                        index: "a2",
                        roundness: { type: 2 },
                        seed: 3,
                        version: 1,
                        versionNonce: 3,
                        isDeleted: false,
                        boundElements: null,
                        updated: Date.now(),
                        link: null,
                        locked: false,
                        startBinding: null,
                        endBinding: null,
                        lastCommittedPoint: null,
                        startArrowhead: null,
                        endArrowhead: "arrow",
                        elbowed: false,
                    },
                    {
                        type: "ellipse",
                        id: "test-ellipse-1",
                        x: 420, y: 110, width: 140, height: 100,
                        strokeColor: "#1e1e1e",
                        backgroundColor: "#b2f2bb",
                        fillStyle: "solid",
                        strokeWidth: 2,
                        roughness: 1,
                        opacity: 100,
                        angle: 0,
                        groupIds: [],
                        frameId: null,
                        index: "a3",
                        roundness: { type: 2 },
                        seed: 4,
                        version: 1,
                        versionNonce: 4,
                        isDeleted: false,
                        boundElements: null,
                        updated: Date.now(),
                        link: null,
                        locked: false,
                    },
                ]
            });
        }""")
        print("Drawing elements injected")
        page.wait_for_timeout(2000)

        # ── Step 5: Advance through remaining questions and finish ──
        for i in range(len(questions)):
            print(f"Advancing Q{i+1}...")
            for btn_label in ["Next", "Finish"]:
                try:
                    page.wait_for_selector(
                        f"button:has-text('{btn_label}'):not([disabled])",
                        timeout=30000
                    )
                    page.click(f"button:has-text('{btn_label}')")
                    print(f"  Clicked '{btn_label}'")
                    page.wait_for_timeout(1500)
                    break
                except:
                    pass

        # ── Step 6: Poll API until report is ready ──
        print("\nPolling for report...")
        for attempt in range(40):
            time.sleep(3)
            r = requests.get(f"{BASE_IM}/api/interview/session/{session_id}")
            data = r.json()
            status = data.get("status")
            has_report = bool(data.get("report"))
            print(f"  t={attempt*3+3}s status={status} report={has_report}")
            if status == "completed" and has_report:
                print("  Report ready")
                break
        else:
            raise TimeoutError("Report generation timed out")

        # ── Step 7: Navigate to report ──
        report_url = f"{FRONTEND}/report/{session_id}"
        print(f"\nOpening report: {report_url}")
        page.goto(report_url, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # ── Step 8: Expand Q1 (the one with the drawing) ──
        print("Expanding Q1 in report...")
        q_buttons = page.locator(".card button").all()
        print(f"  Found {len(q_buttons)} question cards")
        if q_buttons:
            q_buttons[0].click()
            page.wait_for_timeout(2000)

        # ── Step 9: Assert drawing image is visible ──
        print("Checking for drawing image...")
        draw_img = page.locator('[data-testid="draw-image"]')
        expect(draw_img).to_be_visible(timeout=10000)
        print("  Drawing image visible in report")

        # ── Step 10: Assert drawing analysis text is present ──
        print("Checking for drawing analysis text...")
        draw_analysis = page.locator('[data-testid="draw-analysis"]')
        expect(draw_analysis).to_be_visible(timeout=10000)
        analysis_text = draw_analysis.text_content()
        assert len(analysis_text) > 10, f"Drawing analysis too short: {analysis_text}"
        print(f"  Drawing analysis present: {analysis_text[:100]}...")

        # Scroll to show the drawing in the report
        draw_img.scroll_into_view_if_needed()
        page.wait_for_timeout(2000)

        print("\n=== ALL ASSERTIONS PASSED ===")

        context.close()
        browser.close()


if __name__ == "__main__":
    test_draw_tab_e2e()
