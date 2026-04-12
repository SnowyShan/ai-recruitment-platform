from typing import Optional
import os, json, math
from dotenv import load_dotenv

load_dotenv()

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

MAX_TEXT_LENGTH = 10000


def truncate_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Truncate text to maximum length with ellipsis if needed."""
    if not text:
        return text
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text


def _claude_retry():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )


# ── Domain inference ──────────────────────────────────────────────────────────

_DOMAIN_KEYWORDS = {
    "ios": ["ios", "swift", "objective-c", "xcode", "uikit", "swiftui", "apple"],
    "android": ["android", "kotlin", "java mobile"],
    "backend": [
        "backend",
        "back-end",
        "python",
        "django",
        "fastapi",
        "node.js",
        "golang",
        "go developer",
        "rust",
        "api developer",
        "server-side",
    ],
    "frontend": [
        "frontend",
        "front-end",
        "react",
        "vue",
        "angular",
        "javascript developer",
        "typescript developer",
        "ui engineer",
    ],
    "fullstack": ["full stack", "fullstack", "full-stack"],
    "data": [
        "data scientist",
        "machine learning",
        "ml engineer",
        "ai engineer",
        "data engineer",
        "analytics engineer",
    ],
    "devops": [
        "devops",
        "site reliability",
        "sre ",
        "kubernetes",
        "docker",
        "aws engineer",
        "cloud engineer",
        "platform engineer",
        "infrastructure",
    ],
    "mobile": ["mobile developer", "react native", "flutter", "mobile engineer"],
    "security": ["security engineer", "cybersecurity", "appsec", "infosec"],
}


def infer_domain(job_title: str) -> str:
    """Infer technical domain from a job title string."""
    t = job_title.lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return domain
    return "general"


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

DIFFICULTY_LABELS = {
    1: "intern/entry-level",
    2: "junior",
    3: "mid-level",
    4: "senior",
    5: "staff/principal",
}
SENIORITY_LABELS = {
    "junior": "junior engineer",
    "mid": "mid-level engineer",
    "senior": "senior engineer",
    "staff": "staff/principal engineer",
}


def _client():
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-key-here":
        return None
    import anthropic

    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def generate_questions(
    resume_text: str,
    job_description: str,
    difficulty: int,
    num_questions: int,
    hardcoded: Optional[list],
) -> list:
    if hardcoded:
        return [
            {"question": q, "topic": "custom", "expected_depth": "as specified"}
            for q in hardcoded
        ]

    client = _client()
    if not client:
        return _mock_questions(num_questions)

    level = DIFFICULTY_LABELS.get(difficulty, "mid-level")
    prompt = f"""You are a technical interviewer assembling a question set for a structured interview.

Job Description:
{truncate_text(job_description)}

Candidate Resume:
{truncate_text(resume_text)}

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

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )

    resp = _call_api()
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


def evaluate_answer(
    question: str,
    answer: str,
    job_description: str,
    seniority_bar: str,
    hardcoded_answer: Optional[str],
) -> dict:
    client = _client()
    if not client:
        return _mock_evaluation()

    bar = SENIORITY_LABELS.get(seniority_bar, "senior engineer")
    bar_context = (
        f"hardcoded expected answer: {hardcoded_answer}"
        if hardcoded_answer
        else f"expected bar: {bar} level at a top tech company"
    )

    prompt = f"""You are a technical interviewer evaluating a candidate's answer.

Job Description: {truncate_text(job_description)}

Question: {truncate_text(question)}

Candidate's Answer: {truncate_text(answer)}

Evaluation bar: {bar_context}

Evaluate strictly. Return ONLY JSON:
{{
  "score": <0-100>,
  "pass": <true/false>,
  "feedback": "...",
  "what_was_good": "...",
  "what_was_missing": "..."
}}"""

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )

    resp = _call_api()
    text = resp.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])


def generate_report(job_description: str, resume_text: str, qa_pairs: list) -> dict:
    client = _client()
    if not client:
        return _mock_report()

    qa_text = "\n\n".join(
        [
            f"Q: {item['question']}\nA: {item['answer']}\nScore: {item['score']}/100\nFeedback: {item['feedback']}"
            for item in qa_pairs
        ]
    )
    avg = sum(i["score"] for i in qa_pairs) / len(qa_pairs) if qa_pairs else 0

    prompt = f"""You are a senior technical interviewer writing a hiring report.

Job Description: {truncate_text(job_description)}

Resume: {truncate_text(resume_text)}

Interview Q&A:
{truncate_text(qa_text, 8000)}

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

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )

    resp = _call_api()
    text = resp.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])


def generate_coding_question(job_description: str) -> dict:
    """Generate a single logic-based coding question. Language-agnostic, solvable in pseudocode."""
    client = _client()
    if not client:
        return _mock_coding_question()

    prompt = f"""You are a technical interviewer. Generate exactly 1 coding question that tests logic and problem-solving ability.

Job context (for reference only — the question should NOT require any specific API or framework):
{job_description[:500]}

Rules:
1. The question must be solvable in pseudocode or ANY programming language.
2. Do NOT require any specific language, library, API, or framework.
3. Focus on logic, problem decomposition, and algorithmic thinking.
4. The problem should be clear, well-defined, and completable in 10-15 minutes.
5. Include a concrete example with input/output to clarify expectations.
6. Also write a voice_text version: natural, conversational, suitable for text-to-speech.

Return ONLY a single JSON object:
{{"question": "...", "voice_text": "...", "topic": "Coding", "type": "coding"}}"""

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )

    resp = _call_api()
    text = resp.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    q = json.loads(text[start:end])
    q["type"] = "coding"
    return q


def _mock_coding_question() -> dict:
    return {
        "question": "Given a list of numbers, write a function that returns the two numbers that sum closest to a target value. Walk through your approach and explain your reasoning.\n\nExample: nums = [1, 4, 7, 10], target = 12 → Output: [4, 7] (sum = 11, closest to 12)",
        "voice_text": "Here's a coding question for you. Given a list of numbers, write a function that returns the two numbers that sum closest to a target value. For example, given the list 1, 4, 7, 10 and a target of 12, the answer would be 4 and 7 since their sum of 11 is closest to 12. Please walk through your approach and explain your reasoning as you go.",
        "topic": "Coding",
        "type": "coding",
    }


# ── Mock responses when no API key ─────────────────────────────


def _mock_questions(n: int) -> list:
    samples = [
        {
            "question": "Explain how you would design a thread-safe singleton in iOS.",
            "voice_text": "Can you walk me through how you'd design a thread-safe singleton in iOS?",
            "topic": "Concurrency",
            "expected_depth": "Knows DispatchQueue, NSLock approaches",
        },
        {
            "question": "What is the difference between strong, weak, and unowned references?",
            "voice_text": "Can you explain the difference between strong, weak, and unowned references in Swift?",
            "topic": "Memory Management",
            "expected_depth": "ARC, retain cycles, when to use each",
        },
        {
            "question": "How does UITableView reuse cells and why is it important?",
            "voice_text": "How does UITableView handle cell reuse, and why does that matter for performance?",
            "topic": "UIKit",
            "expected_depth": "dequeueReusableCell, memory efficiency",
        },
        {
            "question": "Describe your approach to offline-first architecture in a mobile app.",
            "voice_text": "How would you approach building an offline-first mobile app? Walk me through your thinking.",
            "topic": "Architecture",
            "expected_depth": "Local DB, sync strategy, conflict resolution",
        },
        {
            "question": "How would you optimize an app that scrolls poorly at 30fps?",
            "voice_text": "If an app was scrolling poorly at around 30 frames per second, how would you go about diagnosing and fixing that?",
            "topic": "Performance",
            "expected_depth": "Instruments, off-main-thread rendering, cell pre-sizing",
        },
        {
            "question": "What are the trade-offs between SwiftUI and UIKit?",
            "voice_text": "Can you walk me through the main trade-offs between SwiftUI and UIKit, and when you'd pick one over the other?",
            "topic": "Frameworks",
            "expected_depth": "Maturity, interop, state management",
        },
        {
            "question": "How do you handle API errors gracefully in production?",
            "voice_text": "How do you handle API errors gracefully in a production app?",
            "topic": "Networking",
            "expected_depth": "Retry logic, user feedback, logging",
        },
        {
            "question": "Walk me through how you would architect a large-scale iOS app.",
            "voice_text": "How would you architect a large-scale iOS app? Walk me through your approach.",
            "topic": "System Design",
            "expected_depth": "Modularity, dependency injection, testability",
        },
    ]
    return samples[:n]


def _mock_evaluation() -> dict:
    return {
        "score": 72,
        "pass": True,
        "feedback": "Mock evaluation — add API key for real feedback.",
        "what_was_good": "Answered the question",
        "what_was_missing": "More depth needed",
    }


def _mock_report() -> dict:
    return {
        "overall_score": 72,
        "pass": True,
        "summary": "Mock report — add API key for real analysis.",
        "strengths": ["Communicates clearly"],
        "weaknesses": ["Needs more depth"],
        "hiring_recommendation": "Consider for next round.",
        "per_question": [],
    }


def generate_report_from_transcript(
    job_description: str,
    resume_text: str,
    questions: list,
    full_transcript: str,
    evaluation_prompt: str = "",
    code_answers: dict = None,
    draw_answers: list = None,
    proctoring_data: dict = None,
) -> dict:
    client = _client()
    if not client:
        return _mock_report()

    code_answers = code_answers or {}
    draw_answers = draw_answers or []

    questions_list = ""
    for i, q in enumerate(questions):
        questions_list += f"Q{i + 1}: {q['question']}"
        if q.get("type") == "coding":
            questions_list += "  [CODING QUESTION]"
        questions_list += "\n"

    # Build code submissions section — only include non-empty submissions
    code_section = ""
    non_empty_code = {k: v for k, v in code_answers.items() if v and v.strip()}
    if non_empty_code:
        code_section = "\n\nCode Submissions (from the code editor):\n"
        for idx_str, code in non_empty_code.items():
            code_section += f"--- Q{int(idx_str) + 1} Code Answer ---\n{code}\n---\n\n"

    guidelines = (
        evaluation_prompt.strip()
        if evaluation_prompt.strip()
        else "Evaluate answers fairly based on technical correctness and depth. For skipped questions, score 0."
    )

    core_competency_guidelines = """
For questions marked [CORE_COMPETENCY] in the transcript, also return a "core_competency_probes" array in that question's per_question entry: [{"question": "...", "candidate_answer": "...", "expected_answer": "...", "pass": true/false}]. Parse these from [PROBE_N: ...] markers in the transcript."""

    code_eval_guidelines = ""
    if non_empty_code:
        code_eval_guidelines = """
For questions with submitted code:
- Analyze the code focusing on: logical correctness, problem decomposition, edge case awareness, and clarity of thinking.
- Do NOT penalize for syntax errors or language-specific style issues.
- Include a "code_analysis" field in the per_question entry with your analysis of the submitted code."""

    # Check which questions have drawings
    non_empty_draws = {}
    for i, da in enumerate(draw_answers):
        if da and isinstance(da, str) and len(da) > 0:
            non_empty_draws[i] = da

    draw_eval_guidelines = ""
    draw_section = ""
    if non_empty_draws:
        draw_section = "\n\nDrawing Submissions (from the whiteboard canvas):\n"
        for idx, _ in non_empty_draws.items():
            draw_section += f"- Q{idx + 1}: Drawing submitted (see attached image)\n"
        draw_eval_guidelines = """
For questions with submitted drawings:
- Analyze what the candidate drew: diagrams, flowcharts, architecture, data structures, etc.
- Evaluate whether the drawing demonstrates understanding of the question and clear visual communication.
- Include a "draw_analysis" field in the per_question entry with your analysis of the submitted drawing."""

    ai_assist_guidelines = """

AI-Assist Suspicion Detection:
Some candidates use AI cheating tools (e.g. ParakeetAI, Interview Coder, Final Round AI) during interviews. These tools capture system audio, generate real-time AI answers, and display them as invisible overlays — they cannot be detected by browser proctoring alone. You must evaluate the transcript for behavioral signals that suggest AI assistance.

Signals to look for:
- Answers that are unusually polished and well-structured for spoken verbal responses (no filler words like "um", "uh", "you know", no self-corrections, no natural pauses or restarts)
- Answers that cover edge cases and nuances proactively, as if reading from a written essay rather than thinking out loud
- Perfectly uniform answer length and depth across all questions, including behavioral ones (genuine candidates vary significantly)
- Technical answers that feel like textbook definitions — correct but impersonal, with no reference to personal experience, specific projects, or anecdotes
- Zero hesitation on hard questions that would cause even strong candidates to think before answering
- Answers that start immediately with a perfectly organized structure (e.g. "There are three main points: first... second... third...") without any warm-up

Important context:
- A genuinely strong candidate can have some of these traits. Do not flag someone just for being good.
- Flag when MULTIPLE signals appear consistently across MULTIPLE questions.
- If flagging, explain specifically which answers triggered concern and why.

Add a "ai_assist_suspicion" field to "proctoring_summary":
- "none" — no concern
- "low" — one or two mild signals, not conclusive
- "medium" — several consistent signals across multiple questions, warrants human review
- "high" — strong and consistent signals across the interview; highly suspicious
Also add "ai_assist_notes" with a brief explanation of what you observed (or "No suspicious patterns detected." if none).
"""

    # Build proctoring summary for the prompt
    proctoring_section = ""
    if proctoring_data:
        events = proctoring_data.get("events", [])
        stats = proctoring_data.get("face_detection_stats", {})

        parts = []
        if events:
            event_lines = "\n".join(
                f"  [{e.get('ts_label', '?')}] {e.get('type', '?')}: {e.get('detail', '')}"
                for e in events
            )
            parts.append(f"Proctoring Events:\n{event_lines}")

        if stats:
            stat_lines = (
                f"  Face detection runs: {stats.get('total_runs', 0)}\n"
                f"  Face present: {stats.get('face_detected', 0)}/{stats.get('total_runs', 0)}\n"
                f"  Face absent: {stats.get('face_absent', 0)}/{stats.get('total_runs', 0)}\n"
                f"  Multiple faces: {stats.get('multiple_faces', 0)}/{stats.get('total_runs', 0)}\n"
                f"  Identity checks: {stats.get('identity_check_runs', 0)}, matched: {stats.get('identity_match', 0)}, mismatched: {stats.get('identity_mismatch', 0)}"
            )
            parts.append(f"Face Detection Stats:\n{stat_lines}")

        if parts:
            proctoring_section = "\n\nProctoring Data (for context):\n" + "\n\n".join(
                parts
            )

    prompt_text = f"""You are a senior technical interviewer writing a hiring evaluation report.

Job Description:
{truncate_text(job_description)}

Candidate Resume:
{truncate_text(resume_text)}

Interview Questions:
{truncate_text(questions_list, 5000)}

Full Interview Transcript (questions marked with [Q1:], [Q2:] etc, [SKIPPED] means candidate skipped):
{truncate_text(full_transcript)}{code_section[:2000] if code_section else ""}{draw_section}{proctoring_section}

Evaluation guidelines:
{guidelines}{code_eval_guidelines}{draw_eval_guidelines}{core_competency_guidelines}{ai_assist_guidelines}

Return ONLY valid JSON in this exact format:
{{
  "overall_score": <0-100>,
  "pass": <true/false>,
  "summary": "...",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "hiring_recommendation": "...",
  "proctoring_summary": {{
    "risk_level": "low" | "medium" | "high",
    "flags": ["...", "..."],
    "notes": "...",
    "ai_assist_suspicion": "none" | "low" | "medium" | "high",
    "ai_assist_notes": "..."
  }},
  "per_question": [
    {{
      "question": "...",
      "score": <0-100>,
      "feedback": "...",
      "what_was_good": "...",
      "what_was_missing": "..."
    }}
  ]
}}
Note: "code_analysis" should only be present for questions that have a non-empty code submission. "draw_analysis" should only be present for questions that have a drawing submission. Omit both for other questions.
For "proctoring_summary": if no proctoring events were logged, set risk_level to "low", flags to [], notes to "No issues detected." Base risk_level on frequency/severity of tab switches, face absences, and multiple-face events. For ai_assist_suspicion: evaluate behavioral patterns in the transcript as described above. Default to "none" if the transcript is absent or too short to evaluate."""

    # Build multimodal content blocks when drawings are present
    if non_empty_draws:
        content_blocks = [{"type": "text", "text": prompt_text}]
        for idx, b64_png in non_empty_draws.items():
            content_blocks.append(
                {"type": "text", "text": f"\n--- Q{idx + 1} Drawing ---"}
            )
            content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64_png,
                    },
                }
            )
        message_content = content_blocks
    else:
        message_content = prompt_text

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=3000,
            messages=[{"role": "user", "content": message_content}],
            timeout=120.0,
        )

    resp = _call_api()
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


def generate_behavioral_questions(
    resume_text: str, job_description: str, num_questions: int
) -> list:
    """Generate behavioral/resume-based questions tailored to a specific candidate."""
    if num_questions <= 0:
        return []

    client = _client()
    if not client:
        return _mock_behavioral_questions(num_questions)

    prompt = f"""You are a skilled behavioral interviewer generating questions for a specific candidate.

Job Description:
{truncate_text(job_description)}

Candidate Resume:
{truncate_text(resume_text)}

Generate exactly {num_questions} behavioral interview questions tailored to THIS candidate's specific background.

Rules:
1. Reference specific projects, roles, technologies, or achievements from their resume.
2. Use "Tell me about a time when..." or "Walk me through how you handled..." phrasing.
3. Cover different behavioral competencies: leadership, collaboration, problem-solving, adaptability, ownership.
4. Each question must be distinct — no overlap in the competency being tested.
5. Write a voice_text version of each question: natural, conversational, no special characters, suitable for text-to-speech.

Return ONLY a JSON array:
[{{"question": "...", "voice_text": "...", "topic": "Behavioral", "type": "behavioral"}}]"""

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )

    resp = _call_api()
    text = resp.content[0].text.strip()
    start, end = text.find("["), text.rfind("]") + 1
    questions = json.loads(text[start:end])

    for q in questions:
        q["type"] = "behavioral"
    return questions[:num_questions]


def generate_probes(question: str, topic: str, job_description: str) -> list:
    """Generate exactly 2 probe questions for a core competency question."""
    client = _client()
    if not client:
        return _mock_probes()

    prompt = f"""You are a technical interviewer generating follow-up probe questions for a core competency question.

Main Question: {truncate_text(question)}
Topic: {topic}
Job Description: {truncate_text(job_description)}

Generate exactly 2 probe questions that:
1. Each probe must have a narrow, verifiable expected answer (short text or binary yes/no)
2. At least one probe should use presentation_mode "code" if the topic lends itself to it (memory management, algorithms, data structures, concurrency) — include a short code snippet (<=8 lines)
3. Probes test the same concept from a different angle — not a repeat of the main question
4. Code snippets must be short, self-contained, and directly relevant

Return ONLY a JSON array with exactly 2 items, each with this structure:
[
  {{
    "question": "Display text for the probe",
    "voice_text": "Natural spoken version of the question",
    "presentation_mode": "voice" or "code",
    "code_snippet": null or "short code here",
    "expected_answer": "the correct answer",
    "acceptance_criteria": "What the candidate must demonstrate",
    "answer_type": "binary" or "short_text"
  }}
]"""

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )

    resp = _call_api()
    text = resp.content[0].text.strip()
    start, end = text.find("["), text.rfind("]") + 1
    return json.loads(text[start:end])


def _mock_probes() -> list:
    return [
        {
            "question": "Can you explain the underlying mechanism in more detail?",
            "voice_text": "Can you explain the underlying mechanism in a bit more detail?",
            "presentation_mode": "voice",
            "code_snippet": None,
            "expected_answer": "Detailed explanation of the mechanism",
            "acceptance_criteria": "Candidate demonstrates understanding beyond surface-level knowledge",
            "answer_type": "short_text",
        },
        {
            "question": "What would happen if this constraint were removed?",
            "voice_text": "What would happen if that constraint were removed?",
            "presentation_mode": "voice",
            "code_snippet": None,
            "expected_answer": "Identifies the consequence of removing the constraint",
            "acceptance_criteria": "Candidate can reason about edge cases and system behavior",
            "answer_type": "short_text",
        },
    ]


def assess_answer_depth(
    question: str, answer: str, job_description: str, seniority_bar: str
) -> dict:
    """Fast assessment: does the candidate's answer have enough signal to skip probes?"""
    client = _client()
    if not client:
        return {"needs_probing": True, "reason": "No API key — defaulting to probe."}

    bar = SENIORITY_LABELS.get(seniority_bar, "senior engineer")

    prompt = f"""You are a technical interviewer doing a quick depth check on a candidate's answer.

Question: {truncate_text(question)}
Candidate's Answer: {truncate_text(answer)}
Job Description: {truncate_text(job_description)}
Seniority bar: {bar}

Rules:
- needs_probing: false if the answer is >= 2 sentences AND demonstrates conceptual understanding
- needs_probing: true if the answer is vague, off-topic, very short, or just buzzwords
- Skip probes if the answer is already thorough

Return ONLY JSON:
{{"needs_probing": true/false, "reason": "brief explanation"}}"""

    @_claude_retry()
    def _call_api():
        return client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )

    resp = _call_api()
    text = resp.content[0].text.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])


def _mock_behavioral_questions(n: int) -> list:
    samples = [
        {
            "question": "Tell me about a time when you had to debug a critical production issue under pressure.",
            "voice_text": "Can you walk me through a time when you had to debug a critical production issue under pressure? What did you do?",
            "topic": "Behavioral",
            "type": "behavioral",
        },
        {
            "question": "Describe a situation where you had to push back on a technical decision made by your manager.",
            "voice_text": "Tell me about a situation where you disagreed with a technical decision made by your manager. How did you handle it?",
            "topic": "Behavioral",
            "type": "behavioral",
        },
        {
            "question": "Tell me about a time you mentored or helped a junior team member grow.",
            "voice_text": "Can you tell me about a time when you helped a junior teammate grow or improve their skills?",
            "topic": "Behavioral",
            "type": "behavioral",
        },
    ]
    return samples[:n]
