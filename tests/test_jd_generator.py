"""
E2E test for the AI Job Description Generator.

Tests (API only, fast):
  1. POST /jobs/generate-description with valid prompt → 200 + description len > 200
  2. Description contains tech keywords from prompt
  3. Description has responsibilities + requirements sections
  4. Empty prompt → 422 validation error
  5. Response time < 30 seconds

Tests (browser):
  6. Generate button visible on job creation form
  7. Clicking Generate fills the description textarea

REQUIREMENTS: All 4 services running. Real Claude key.
"""
import pytest
import requests
import time
import uuid
from playwright.sync_api import Playwright

# Configuration
TB_API = "http://localhost:8000/api"
TB_FRONTEND = "http://localhost:5173"
INTERVIEW_API = "http://localhost:8001/api"
INTERVIEW_FRONTEND = "http://localhost:5174"
ADMIN_API_KEY = "test-admin-key-123"

# Test user (run ID suffix to avoid collisions)
_RUN_ID = uuid.uuid4().hex[:8]
TEST_EMAIL = f"recruiter.jd_{_RUN_ID}@example.com"
TEST_PASSWORD = "password123"

def setup_admin_user():
    """Create a test recruiter user if it doesn't exist."""
    try:
        response = requests.post(
            f"{TB_API}/auth/register",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "full_name": f"JD Generator Tester {_RUN_ID}",
                "company_name": "Test Company",
            },
            timeout=10,
        )
        if response.status_code in [200, 400]:
            print(f"✓ User {TEST_EMAIL} ready or exists")
        else:
            print(f"✗ Failed to create user: {response.status_code}")
    except Exception as e:
        print(f"✗ Setup failed: {e}")


def login_and_get_token():
    """Login and return auth token."""
    response = requests.post(
        f"{TB_API}/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
        timeout=10,
    )
    if response.status_code != 200:
        raise Exception(f"Login failed: {response.status_code}")
    return response.json().get("access_token")


def create_job(token):
    """Create a test job."""
    response = requests.post(
        f"{TB_API}/jobs",
        json={
            "title": f"Test Job JD Generator {_RUN_ID}",
            "description": "Initial description",
            "department": "Engineering",
            "location": "San Francisco",
            "job_type": "full_time",
            "experience_level": "senior",
            "salary_min": 100000,
            "salary_max": 150000,
        },
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if response.status_code != 201:
        raise Exception(f"Job creation failed: {response.status_code}")
    return response.json()


def cleanup_job(token, job_id):
    """Delete test job after test."""
    try:
        requests.delete(
            f"{TB_API}/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        print(f"✓ Cleaned up job {job_id}")
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")


# ── API Tests ───────────────────────────────────────────────────────


def test_jd_generate_valid_prompt():
    """Test 1: POST with valid prompt returns 200 + description"""
    setup_admin_user()
    token = login_and_get_token()
    
    start = time.time()
    response = requests.post(
        f"{TB_API}/jobs/generate-description",
        json={
            "prompt": "Senior iOS Engineer, SwiftUI + on-device ML, 5+ years"
        },
        timeout=35,
    )
    elapsed = time.time() - start
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "description" in data, "Response missing 'description'"
    
    description = data["description"]
    assert len(description) > 200, f"Description too short: {len(description)} chars"
    
    # Check for expected content
    assert any(
        kw in description.lower() 
        for kw in ["ios", "swift", "swiftui", "ml", "machine learning", "on-device"]
    ), "Missing tech keywords in description"
    
    assert any(
        section in description.lower() 
        for section in ["responsibilities", "you'll do", "what you'll", "requirements", "looking for", "skills"]
    ), "Missing responsibilities or requirements sections"
    
    assert elapsed < 30, f"Response too slow: {elapsed:.1f}s"


def test_jd_generate_empty_prompt():
    """Test 4: Empty prompt returns 422"""
    response = requests.post(
        f"{TB_API}/jobs/generate-description",
        json={"prompt": ""},
        timeout=10,
    )
    
    assert response.status_code == 422, f"Expected 422 for empty prompt, got {response.status_code}"


def test_jd_generate_with_various_prompts():
    """Test 2: Description contains tech keywords from various prompts"""
    test_prompts = [
        "Senior Python Developer, Django, FastAPI",
        "React Frontend Developer, TypeScript, 3 years",
        "DevOps Engineer, Kubernetes, Docker",
    ]
    
    for prompt in test_prompts:
        response = requests.post(
            f"{TB_API}/jobs/generate-description",
            json={"prompt": prompt},
            timeout=35,
        )
        assert response.status_code == 200, f"Prompt failed: {prompt}"
        data = response.json()
        description = data["description"].lower()
        
        # Verify at least one keyword from prompt appears in description
        prompt_lower = prompt.lower()
        has_keyword = any(kw in description for kw in prompt_lower.split())
        assert has_keyword, f"No keywords from '{prompt}' in description"


# ── Browser Tests ───────────────────────────────────────────────


def test_jd_button_visible_on_create():
    """Test 6: Generate button visible on job creation form"""
    with Playwright() as p:
        p.goto(f"{TB_FRONTEND}/login")
        p.fill('input[type="email"]', TEST_EMAIL)
        p.fill('input[type="password"]', TEST_PASSWORD)
        p.click('button[type="submit"]')
        p.wait_for_url(f"{TB_FRONTEND}/**", timeout=10000)
        
        # Navigate to jobs page
        p.goto(f"{TB_FRONTEND}/jobs")
        p.click('button:has-text("Create Job")')
        p.wait_for_selector('textarea[name="description"]', timeout=10000)
        
        # Check for JD Generator elements
        assert p.locator('text=/Generate with AI/').is_visible(timeout=5000)
        assert p.locator('input[placeholder*="Generate with AI"]').is_visible(timeout=5000)
        assert p.locator('button:has-text("Generate")').is_visible(timeout=5000)


def test_jd_click_generate_fills_textarea():
    """Test 7: Clicking Generate fills the description textarea"""
    with Playwright() as p:
        # Login
        p.goto(f"{TB_FRONTEND}/login")
        p.fill('input[type="email"]', TEST_EMAIL)
        p.fill('input[type="password"]', TEST_PASSWORD)
        p.click('button[type="submit"]')
        p.wait_for_url(f"{TB_FRONTEND}/**", timeout=10000)
        
        # Navigate to create job
        p.goto(f"{TB_FRONTEND}/jobs")
        p.click('button:has-text("Create Job")')
        p.wait_for_selector('textarea[name="description"]', timeout=10000)
        
        # Initial description value
        textarea = p.locator('textarea[name="description"]')
        initial_value = textarea.input_value()
        
        # Fill JD prompt and click Generate
        prompt_input = p.locator('input[placeholder*="Generate with AI"]')
        prompt_input.fill("Senior React Developer, TypeScript, Redux")
        generate_btn = p.locator('button:has-text("✨ Generate")')
        generate_btn.click()
        
        # Wait for generation to complete (button text changes)
        p.wait_for_selector('button:has-text("✨ Generate")', state='attached', timeout=30000)
        
        # Check that description was updated
        final_value = textarea.input_value()
        assert final_value != initial_value, "Description not updated"
        assert len(final_value) > initial_value, "Description not longer"
        
        # Verify it contains expected content
        final_lower = final_value.lower()
        assert any(kw in final_lower for kw in ["react", "typescript", "redux"])


if __name__ == "__main__":
    print("=" * 60)
    print("TalentBridge JD Generator Tests")
    print("=" * 60)
    
    # API tests
    test_jd_generate_valid_prompt()
    print("✓ test_jd_generate_valid_prompt")
    
    test_jd_generate_empty_prompt()
    print("✓ test_jd_generate_empty_prompt")
    
    test_jd_generate_with_various_prompts()
    print("✓ test_jd_generate_with_various_prompts")
    
    print("\nAll API tests passed!")
