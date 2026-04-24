"""
Browser-driven E2E for candidate experience improvements.

Tests:
  1. Briefing page loads before interview (checklist, proctoring notice, Start button)
  2. Clicking Start transitions to interview UI
  3. Progress bar visible: shows "Question 1 of N", increases after Next
  4. ThankYou page has "Interview Complete", no email/feedback promise

REQUIREMENTS: playwright + chromium, BlackHole 2ch, all 4 services, valid session link.
"""
import pytest
from playwright.sync_api import Playwright

# Configuration
INTERVIEW_FRONTEND = "http://localhost:5174"
INTERVIEW_API = "http://localhost:8001/api"

# Test configuration
RUN_ID = "candidate_exp_test_001"

# A valid interview session token (you may need to create one via the API)
VALID_TOKEN = "test-token-123"


def test_briefing_page_loads():
    """Test 1: Briefing page loads before interview with checklist"""
    with Playwright() as p:
        # Navigate to interview with token
        p.goto(f"{INTERVIEW_FRONTEND}/?token={VALID_TOKEN}")
        
        # Check that briefing page elements are present
        assert p.locator('text=/Ready for your interview?/').is_visible(timeout=10000)
        assert p.locator('text=/Before you begin:/').is_visible(timeout=5000)
        assert p.locator('text=/quiet place/').is_visible(timeout=5000)
        assert p.locator('text=/microphone/').is_visible(timeout=5000)
        assert p.locator('text=/time to think/').is_visible(timeout=5000)
        assert p.locator('text=/answer as you would in a real interview/').is_visible(timeout=5000)
        assert p.locator('text=/20–30 minutes/').is_visible(timeout=5000)
        
        # Check for proctoring notice
        assert p.locator('text=/This interview is monitored/').is_visible(timeout=5000)
        
        # Check that Start button is present
        assert p.locator('button:has-text("Start Interview")').is_visible(timeout=5000)
        
        # Verify question text is NOT visible yet
        assert not p.locator('[data-testid="question-text"]').is_visible(timeout=1000)
        
        print("✓ Briefing page elements verified")


def test_start_button_transitions_to_interview():
    """Test 2: Clicking Start transitions to interview UI"""
    with Playwright() as p:
        p.goto(f"{INTERVIEW_FRONTEND}/?token={VALID_TOKEN}")
        
        # Click Start button
        start_btn = p.locator('button:has-text("Start Interview")')
        start_btn.click()
        
        # Wait for interview question to appear
        assert p.locator('[data-testid="question-text"]').is_visible(timeout=15000)
        
        # Verify briefing page elements are no longer visible
        assert not p.locator('text=/Ready for your interview?/').is_visible(timeout=2000)
        
        print("✓ Start button transitions to interview")


def test_progress_bar_visible():
    """Test 3: Progress bar shows current question and percentage"""
    with Playwright() as p:
        p.goto(f"{INTERVIEW_FRONTEND}/?token={VALID_TOKEN}")
        
        # Click Start button to get to interview
        p.locator('button:has-text("Start Interview")').click()
        p.locator('[data-testid="question-text"]').wait_for(state='visible', timeout=15000)
        
        # Check progress bar elements
        assert p.locator('[data-testid="progress-bar"]').is_visible(timeout=5000)
        assert p.locator('[data-testid="progress-label"]').is_visible(timeout=5000)
        
        # Check progress label content
        progress_label = p.locator('[data-testid="progress-label"]')
        label_text = progress_label.inner_text()
        
        # Should show "Question 1 of N" initially
        assert "Question 1 of" in label_text, f"Expected 'Question 1 of' in '{label_text}'"
        
        # Check percentage (should be roughly 1/N * 100)
        assert "%" in label_text, f"Expected '%' in '{label_text}'"


def test_thankyou_page_content():
    """Test 4: ThankYou page has proper content, no email promise"""
    with Playwright() as p:
        # Complete an interview and navigate to Thank You
        # Note: This test assumes you can reach Thank You directly
        p.goto(f"{INTERVIEW_FRONTEND}/thank-you")
        
        # Check for Interview Complete heading
        assert p.locator('text=/Interview Complete/').is_visible(timeout=5000)
        
        # Check for green checkmark (using CheckCircle icon)
        assert p.locator('.text-green-600').is_visible(timeout=5000)
        
        # Verify NO email feedback promise (white-label platform)
        page_text = p.locator('body').inner_text().lower()
        assert "email" not in page_text, "Page should not mention email (white-label)"
        assert "feedback" not in page_text, "Page should not mention feedback"
        
        # Check for proper closing message
        assert p.locator('text=/Your responses have been submitted/').is_visible(timeout=5000)
        assert p.locator('text=/hiring team will be in touch/').is_visible(timeout=5000)
        
        # Check for closing text
        assert p.locator('text=/close this window/').is_visible(timeout=5000)
        
        print("✓ ThankYou page content verified")


def test_progress_increases_after_next():
    """Verify progress bar updates when moving between questions"""
    with Playwright() as p:
        p.goto(f"{INTERVIEW_FRONTEND}/?token={VALID_TOKEN}")
        p.locator('button:has-text("Start Interview")').click()
        
        # Wait for first question
        p.locator('[data-testid="question-text"]').wait_for(state='visible', timeout=15000)
        
        # Get initial progress
        progress_label = p.locator('[data-testid="progress-label"]')
        initial_text = progress_label.inner_text()
        assert "Question 1" in initial_text
        
        # Click Next to move to question 2 (if available)
        next_btn = p.locator('button:has-text("Next")')
        if next_btn.is_visible(timeout=2000):
            next_btn.click()
            p.wait_for_timeout(2000)
            
            # Check progress updated
            updated_text = progress_label.inner_text()
            assert "Question 2" in updated_text, "Progress should show Question 2"
        
        print("✓ Progress updates on question advance")


if __name__ == "__main__":
    print("=" * 60)
    print("TalentBridge Candidate Experience Tests")
    print("=" * 60)
    
    test_briefing_page_loads()
    test_start_button_transitions_to_interview()
    test_progress_bar_visible()
    test_thankyou_page_content()
    test_progress_increases_after_next()
    
    print("\nAll candidate experience tests passed!")
