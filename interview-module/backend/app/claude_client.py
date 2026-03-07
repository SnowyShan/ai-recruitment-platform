from typing import Optional
import os, json, math
from dotenv import load_dotenv
load_dotenv()

# ── Domain inference ──────────────────────────────────────────────────────────

_DOMAIN_KEYWORDS = {
    'ios':       ['ios', 'swift', 'objective-c', 'xcode', 'uikit', 'swiftui', 'apple'],
    'android':   ['android', 'kotlin', 'java mobile'],
    'backend':   ['backend', 'back-end', 'python', 'django', 'fastapi', 'node.js', 'golang',
                  'go developer', 'rust', 'api developer', 'server-side'],
    'frontend':  ['frontend', 'front-end', 'react', 'vue', 'angular', 'javascript developer',
                  'typescript developer', 'ui engineer'],
    'fullstack': ['full stack', 'fullstack', 'full-stack'],
    'data':      ['data scientist', 'machine learning', 'ml engineer', 'ai engineer',
                  'data engineer', 'analytics engineer'],
    'devops':    ['devops', 'site reliability', 'sre ', 'kubernetes', 'docker', 'aws engineer',
                  'cloud engineer', 'platform engineer', 'infrastructure'],
    'mobile':    ['mobile developer', 'react native', 'flutter', 'mobile engineer'],
    'security':  ['security engineer', 'cybersecurity', 'appsec', 'infosec'],
}

def infer_domain(job_title: str) -> str:
    """Infer technical domain from a job title string."""
    t = job_title.lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return domain
    return 'general'

# ── TTS to disk ───────────────────────────────────────────────────────────────

def generate_and_store_tts(text: str, audio_path: str, voice: str = "nova") -> bool:
    """Generate TTS audio via OpenAI and save to disk. Returns True on success."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or not text.strip():
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice=voice,
            input=text.strip(),
        )
        os.makedirs(os.path.dirname(audio_path), exist_ok=True)
        response.stream_to_file(audio_path)
        return True
    except Exception as e:
        print(f"[TTS] Failed to generate audio for path {audio_path}: {e}")
        return False

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

DIFFICULTY_LABELS = {1: "intern/entry-level", 2: "junior", 3: "mid-level", 4: "senior", 5: "staff/principal"}
SENIORITY_LABELS = {"junior": "junior engineer", "mid": "mid-level engineer", "senior": "senior engineer", "staff": "staff/principal engineer"}

def _client():
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-key-here":
        return None
    import anthropic
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def generate_questions(resume_text: str, job_description: str, difficulty: int, num_questions: int, hardcoded: Optional[list]) -> list:
    if hardcoded:
        return [{"question": q, "topic": "custom", "expected_depth": "as specified"} for q in hardcoded]

    client = _client()
    if not client:
        return _mock_questions(num_questions)

    level = DIFFICULTY_LABELS.get(difficulty, "mid-level")
    prompt = f"""You are a technical interviewer assembling a question set for a structured interview.

Job Description:
{job_description}

Candidate Resume:
{resume_text}

Difficulty level: {level} (difficulty {difficulty}/5)

Generate exactly {num_questions} interview questions following these rules:
1. Each question must cover a DISTINCT concept or skill area — no two questions should overlap in the core concept being tested. If memory management is tested, do not test it again from a different angle.
2. Assign each question a short topic tag (e.g. "Memory Management", "Concurrency", "Architecture").
3. Before finalising the list, review it and remove any question whose core concept is already covered by another question in the list. Replace it with a question on a different topic.
4. For difficulty 1-2, focus on fundamentals. For 3, balanced technical depth. For 4-5, focus on system design, trade-offs, and deep expertise.
5. Order questions from foundational to advanced.
6. For each question, also write a "voice_text" version — a natural, conversational rephrasing suitable for being read aloud by a voice assistant. The voice_text should:
   - Remove code formatting, backticks, and symbols that sound awkward when spoken
   - Use conversational phrasing ("Can you walk me through..." instead of "Explain...")
   - Be slightly warmer and more natural in tone
   - Be roughly the same length or slightly shorter than the screen question

Return ONLY a JSON array like:
[{{"question": "...", "voice_text": "...", "topic": "...", "expected_depth": "..."}}]"""

    resp = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    start, end = text.find("["), text.rfind("]") + 1
    questions = json.loads(text[start:end])

    # Post-process: deduplicate by both topic AND question text as a safety net
    seen_topics = set()
    seen_questions = set()
    deduped = []
    for q in questions:
        topic_key = q.get("topic", "").lower().strip()
        question_key = q.get("question", "").lower().strip()
        if topic_key not in seen_topics and question_key not in seen_questions:
            seen_topics.add(topic_key)
            seen_questions.add(question_key)
            deduped.append(q)
    return deduped[:num_questions]

def evaluate_answer(question: str, answer: str, job_description: str, seniority_bar: str, hardcoded_answer: Optional[str]) -> dict:
    client = _client()
    if not client:
        return _mock_evaluation()

    bar = SENIORITY_LABELS.get(seniority_bar, "senior engineer")
    bar_context = f"hardcoded expected answer: {hardcoded_answer}" if hardcoded_answer else f"expected bar: {bar} level at a top tech company"

    prompt = f"""You are a technical interviewer evaluating a candidate's answer.

Job Description: {job_description}

Question: {question}

Candidate's Answer: {answer}

Evaluation bar: {bar_context}

Evaluate strictly. Return ONLY JSON:
{{
  "score": <0-100>,
  "pass": <true/false>,
  "feedback": "...",
  "what_was_good": "...",
  "what_was_missing": "..."
}}"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])

def generate_report(job_description: str, resume_text: str, qa_pairs: list) -> dict:
    client = _client()
    if not client:
        return _mock_report()

    qa_text = "\n\n".join([
        f"Q: {item['question']}\nA: {item['answer']}\nScore: {item['score']}/100\nFeedback: {item['feedback']}"
        for item in qa_pairs
    ])
    avg = sum(i["score"] for i in qa_pairs) / len(qa_pairs) if qa_pairs else 0

    prompt = f"""You are a senior technical interviewer writing a hiring report.

Job Description: {job_description}

Resume: {resume_text}

Interview Q&A:
{qa_text}

Average score: {avg:.1f}/100

Write a comprehensive hiring report. Return ONLY JSON:
{{
  "overall_score": <0-100>,
  "pass": <true/false>,
  "summary": "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "hiring_recommendation": "...",
  "per_question": [
    {{"question": "...", "score": 0, "feedback": "...", "what_was_good": "...", "what_was_missing": "..."}}
  ]
}}"""

    resp = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])

# ── Mock responses when no API key ─────────────────────────────

def _mock_questions(n: int) -> list:
    samples = [
        {"question": "Explain how you would design a thread-safe singleton in iOS.", "voice_text": "Can you walk me through how you'd design a thread-safe singleton in iOS?", "topic": "Concurrency", "expected_depth": "Knows DispatchQueue, NSLock approaches"},
        {"question": "What is the difference between strong, weak, and unowned references?", "voice_text": "Can you explain the difference between strong, weak, and unowned references in Swift?", "topic": "Memory Management", "expected_depth": "ARC, retain cycles, when to use each"},
        {"question": "How does UITableView reuse cells and why is it important?", "voice_text": "How does UITableView handle cell reuse, and why does that matter for performance?", "topic": "UIKit", "expected_depth": "dequeueReusableCell, memory efficiency"},
        {"question": "Describe your approach to offline-first architecture in a mobile app.", "voice_text": "How would you approach building an offline-first mobile app? Walk me through your thinking.", "topic": "Architecture", "expected_depth": "Local DB, sync strategy, conflict resolution"},
        {"question": "How would you optimize an app that scrolls poorly at 30fps?", "voice_text": "If an app was scrolling poorly at around 30 frames per second, how would you go about diagnosing and fixing that?", "topic": "Performance", "expected_depth": "Instruments, off-main-thread rendering, cell pre-sizing"},
        {"question": "What are the trade-offs between SwiftUI and UIKit?", "voice_text": "Can you walk me through the main trade-offs between SwiftUI and UIKit, and when you'd pick one over the other?", "topic": "Frameworks", "expected_depth": "Maturity, interop, state management"},
        {"question": "How do you handle API errors gracefully in production?", "voice_text": "How do you handle API errors gracefully in a production app?", "topic": "Networking", "expected_depth": "Retry logic, user feedback, logging"},
        {"question": "Walk me through how you would architect a large-scale iOS app.", "voice_text": "How would you architect a large-scale iOS app? Walk me through your approach.", "topic": "System Design", "expected_depth": "Modularity, dependency injection, testability"},
    ]
    return samples[:n]

def _mock_evaluation() -> dict:
    return {"score": 72, "pass": True, "feedback": "Mock evaluation — add API key for real feedback.", "what_was_good": "Answered the question", "what_was_missing": "More depth needed"}

def _mock_report() -> dict:
    return {"overall_score": 72, "pass": True, "summary": "Mock report — add API key for real analysis.", "strengths": ["Communicates clearly"], "weaknesses": ["Needs more depth"], "hiring_recommendation": "Consider for next round.", "per_question": []}


def generate_report_from_transcript(job_description: str, resume_text: str, questions: list, full_transcript: str, evaluation_prompt: str = "") -> dict:
    client = _client()
    if not client:
        return _mock_report()

    questions_list = "\n".join([f"Q{i+1}: {q['question']}" for i, q in enumerate(questions)])

    guidelines = evaluation_prompt.strip() if evaluation_prompt.strip() else "Evaluate answers fairly based on technical correctness and depth. For skipped questions, score 0."

    prompt = f"""You are a senior technical interviewer writing a hiring evaluation report.

Job Description:
{job_description}

Candidate Resume:
{resume_text}

Interview Questions:
{questions_list}

Full Interview Transcript (questions marked with [Q1:], [Q2:] etc, [SKIPPED] means candidate skipped):
{full_transcript}

Evaluation guidelines:
{guidelines}

Return ONLY valid JSON in this exact format:
{{
  "overall_score": <0-100>,
  "pass": <true/false>,
  "summary": "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "hiring_recommendation": "...",
  "per_question": [
    {{
      "question": "...",
      "score": <0-100>,
      "feedback": "...",
      "what_was_good": "...",
      "what_was_missing": "..."
    }}
  ]
}}"""

    resp = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    result = json.loads(text[start:end])

    # Deduplicate per_question entries — Claude occasionally repeats questions
    seen_pq: set = set()
    deduped_pq = []
    for pq in result.get("per_question", []):
        key = pq.get("question", "").lower().strip()
        if key not in seen_pq:
            seen_pq.add(key)
            deduped_pq.append(pq)
    result["per_question"] = deduped_pq

    return result

# ── Behavioral question generation ────────────────────────────────────────────

def generate_behavioral_questions(resume_text: str, job_description: str, num_questions: int) -> list:
    """Generate behavioral/resume-based questions tailored to a specific candidate."""
    if num_questions <= 0:
        return []

    client = _client()
    if not client:
        return _mock_behavioral_questions(num_questions)

    prompt = f"""You are a skilled behavioral interviewer generating questions for a specific candidate.

Job Description:
{job_description}

Candidate Resume:
{resume_text}

Generate exactly {num_questions} behavioral interview questions tailored to THIS candidate's specific background.

Rules:
1. Reference specific projects, roles, technologies, or achievements from their resume.
2. Use "Tell me about a time when..." or "Walk me through how you handled..." phrasing.
3. Cover different behavioral competencies: leadership, collaboration, problem-solving, adaptability, ownership.
4. Each question must be distinct — no overlap in the competency being tested.
5. Write a voice_text version of each question: natural, conversational, no special characters, suitable for text-to-speech.

Return ONLY a JSON array:
[{{"question": "...", "voice_text": "...", "topic": "Behavioral", "type": "behavioral"}}]"""

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )
    text = resp.content[0].text.strip()
    start, end = text.find("["), text.rfind("]") + 1
    questions = json.loads(text[start:end])

    for q in questions:
        q["type"] = "behavioral"
    return questions[:num_questions]


def _mock_behavioral_questions(n: int) -> list:
    samples = [
        {"question": "Tell me about a time when you had to debug a critical production issue under pressure.", "voice_text": "Can you walk me through a time when you had to debug a critical production issue under pressure? What did you do?", "topic": "Behavioral", "type": "behavioral"},
        {"question": "Describe a situation where you had to push back on a technical decision made by your manager.", "voice_text": "Tell me about a situation where you disagreed with a technical decision made by your manager. How did you handle it?", "topic": "Behavioral", "type": "behavioral"},
        {"question": "Tell me about a time you mentored or helped a junior team member grow.", "voice_text": "Can you tell me about a time when you helped a junior teammate grow or improve their skills?", "topic": "Behavioral", "type": "behavioral"},
    ]
    return samples[:n]
