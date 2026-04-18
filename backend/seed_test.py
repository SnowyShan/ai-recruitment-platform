"""
TalentBridge AI — Test Data Seed
=================================
Creates a complete realistic dataset for testing every feature end-to-end.

RUN:  cd backend && python seed_test.py

ACCOUNTS CREATED
  Admin:     admin@talentbridge.ai     / Admin@123
  Recruiter: recruiter@talentbridge.ai / Recruiter@123

E2E TEST FLOW
  1. Log in as recruiter → Dashboard shows real metrics
  2. Jobs → "Senior Python Engineer" is the test job (active, auto-invite ON ≥70)
  3. Open http://localhost:5173/browse-jobs  (no login needed)
  4. Find "Senior Python Engineer" → click View & Apply
  5. Fill name/email, upload sample_resume.pdf (in this folder)
  6. Submit → Application created, AI scores resume, auto-invite fires if score ≥70
  7. Back in recruiter: Applications → Python Engineer card → see new application
  8. Shortlist it manually → then click ✨ to send screening invite
  9. Screenings → Python Engineer accordion → candidate listed
 10. Notifications bell → screening completion appears
"""

import sys, os, json, uuid
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))

from app.database import engine, Base, SessionLocal
from app import models
from passlib.context import CryptContext
import random

rng = random.Random(99)
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
Base.metadata.create_all(bind=engine)
db = SessionLocal()

def ago(days=0, hours=0):
    return datetime.utcnow() - timedelta(days=days, hours=hours)

def upsert_user(email, name, role, password):
    u = db.query(models.User).filter(models.User.email == email).first()
    if u:
        u.hashed_password = pwd.hash(password); u.role = role; u.is_active = True; u.is_verified = True
        db.commit(); print(f"  ✔ Updated  {email}"); return u
    u = models.User(email=email, full_name=name, company_name="TalentBridge AI",
                    hashed_password=pwd.hash(password), role=role,
                    is_active=True, is_verified=True, created_at=ago(90))
    db.add(u); db.commit(); db.refresh(u)
    print(f"  ✔ Created  {email}  [{role}]"); return u

print("\n🌱  TalentBridge Test Seed\n")

# ── Users ──────────────────────────────────────────────────────────────────
admin     = upsert_user("admin@talentbridge.ai",     "Admin User",  "admin",     "Admin@123")
recruiter = upsert_user("recruiter@talentbridge.ai", "Sarah Chen",  "recruiter", "Recruiter@123")

# ── Jobs ───────────────────────────────────────────────────────────────────
JOBS = [
    dict(title="Senior Python Engineer",       department="Engineering",  location="Remote",          job_type="full_time",  experience_level="senior", salary_min=130000, salary_max=170000,
         description="Build scalable Python microservices powering TalentBridge AI.\nYou will own backend features end-to-end: design, code, deploy.",
         requirements="5+ years Python, FastAPI or Django, PostgreSQL, Docker, AWS.\nStrong systems design skills.",
         skills_required="Python,FastAPI,PostgreSQL,Docker,AWS,Redis",
         domain="backend", setup_status="ready",
         interview_num_questions=8, interview_difficulty=3, interview_seniority="senior",
         interview_behavioral_pct=20, auto_invite_screening=True, auto_invite_threshold=70,
         is_urgent=False, status="active", days_ago=5),

    dict(title="Senior iOS Engineer",           department="Engineering",  location="San Francisco",   job_type="full_time",  experience_level="senior", salary_min=140000, salary_max=185000,
         description="Build and ship features in our iOS app used by 2M+ recruiters.\nYou will architect SwiftUI components and own the App Store release cycle.",
         requirements="5+ years iOS, Swift/SwiftUI, Core Data, CI/CD, App Store submission.",
         skills_required="Swift,SwiftUI,Xcode,Core Data,REST APIs",
         domain="ios", setup_status="ready",
         interview_num_questions=8, interview_difficulty=4, interview_seniority="senior",
         interview_behavioral_pct=25, auto_invite_screening=True, auto_invite_threshold=75,
         is_urgent=True, status="active", days_ago=12),

    dict(title="Data Scientist — ML Platform",  department="Data & AI",    location="Remote",          job_type="full_time",  experience_level="senior", salary_min=145000, salary_max=195000,
         description="Build ML models that power candidate matching and resume scoring.\nWork on NLP, embeddings, and bias detection at scale.",
         requirements="5+ years ML, PyTorch/TF, NLP, MLflow, SQL.",
         skills_required="Python,PyTorch,NLP,MLflow,SQL,AWS SageMaker",
         domain="data", setup_status="ready",
         interview_num_questions=10, interview_difficulty=5, interview_seniority="senior",
         interview_behavioral_pct=15, auto_invite_screening=False, auto_invite_threshold=80,
         is_urgent=False, status="active", days_ago=18),

    dict(title="Product Manager — Growth",       department="Product",      location="New York",        job_type="full_time",  experience_level="mid",    salary_min=130000, salary_max=170000,
         description="Lead growth initiatives on our recruiter-facing product.\nDefine roadmap, write specs, and ship experiments.",
         requirements="3+ years PM, data-driven, B2B SaaS, SQL skills.",
         skills_required="Product Strategy,SQL,A/B Testing,Figma,Jira",
         domain="product", setup_status="ready",
         interview_num_questions=8, interview_difficulty=3, interview_seniority="mid",
         interview_behavioral_pct=40, auto_invite_screening=True, auto_invite_threshold=72,
         is_urgent=False, status="active", days_ago=5),

    dict(title="Senior UX Designer",             department="Design",       location="New York",        job_type="full_time",  experience_level="senior", salary_min=125000, salary_max=160000,
         description="Own end-to-end design for our recruiter dashboard.\nDrive research, IA, prototyping, and design system.",
         requirements="5+ years UX, Figma, design systems, usability testing.",
         skills_required="Figma,Design Systems,User Research,Prototyping,Accessibility",
         domain="design", setup_status="ready",
         interview_num_questions=7, interview_difficulty=3, interview_seniority="senior",
         interview_behavioral_pct=35, auto_invite_screening=False, auto_invite_threshold=75,
         is_urgent=True, status="active", days_ago=21),

    dict(title="Full Stack Engineer (React/Node)", department="Engineering", location="Remote",         job_type="full_time",  experience_level="mid",    salary_min=115000, salary_max=150000,
         description="Build full-stack features across React SPA and Node.js backend.\nOwn features from design through deployment.",
         requirements="3+ years full-stack, React, Node.js/Express, PostgreSQL.",
         skills_required="React,Node.js,TypeScript,PostgreSQL,REST",
         domain="frontend", setup_status="ready",
         interview_num_questions=8, interview_difficulty=3, interview_seniority="mid",
         interview_behavioral_pct=20, auto_invite_screening=True, auto_invite_threshold=70,
         is_urgent=False, status="active", days_ago=4),

    dict(title="DevOps / Platform Engineer",     department="Infrastructure", location="Remote",        job_type="full_time",  experience_level="mid",    salary_min=130000, salary_max=175000,
         description="Build and maintain our cloud infrastructure on AWS.\nKubernetes, Terraform, CI/CD pipelines and observability.",
         requirements="3+ years DevOps, Kubernetes, Terraform, AWS, GitHub Actions.",
         skills_required="Kubernetes,Terraform,AWS,Docker,Prometheus,GitHub Actions",
         domain="backend", setup_status="ready",
         interview_num_questions=8, interview_difficulty=4, interview_seniority="mid",
         interview_behavioral_pct=20, auto_invite_screening=True, auto_invite_threshold=70,
         is_urgent=False, status="active", days_ago=10),

    dict(title="Enterprise Sales Executive",     department="Sales",        location="Chicago",         job_type="full_time",  experience_level="senior", salary_min=100000, salary_max=130000,
         description="Close enterprise deals with Fortune 1000 HR leaders.\nOwn territory, run demos, negotiate contracts, hit $1M+ ARR quota.",
         requirements="5+ years enterprise SaaS sales, HRTech preferred, CRM proficiency.",
         skills_required="Enterprise Sales,Salesforce,SaaS,Negotiation,HR Tech",
         domain="sales", setup_status="ready",
         interview_num_questions=7, interview_difficulty=3, interview_seniority="senior",
         interview_behavioral_pct=50, auto_invite_screening=True, auto_invite_threshold=68,
         is_urgent=False, status="active", days_ago=15),
]

jobs_db = []
for jd in JOBS:
    days = jd.pop("days_ago")
    existing = db.query(models.Job).filter(models.Job.title == jd["title"]).first()
    if existing:
        # Update is_urgent flag in case it changed
        for k, v in jd.items():
            if hasattr(existing, k): setattr(existing, k, v)
        db.commit(); jobs_db.append(existing)
    else:
        j = models.Job(**jd, created_by=recruiter.id, created_at=ago(days), updated_at=ago(days))
        db.add(j); db.commit(); db.refresh(j); jobs_db.append(j)

job_by_title = {j.title: j for j in jobs_db}
print(f"  ✔ Jobs: {len(jobs_db)} active")

# ── Candidates ─────────────────────────────────────────────────────────────
CANDIDATES = [
    # Python / Backend
    ("Tom Reyes",      "tom.reyes@test.com",      "+1-415-555-0201","Remote",          "linkedin",
     "Backend engineer 4 years at Stripe and Cloudflare. Python/FastAPI expert, PostgreSQL query optimisation, Kafka for event streaming, 99.99% uptime SLA delivery.",4.0),
    ("Sara Fischer",   "sara.fischer@test.com",   "+1-206-555-0202","Seattle",         "referral",
     "Full-stack 5 years, Python Django/FastAPI, React, AWS CDK, Terraform. Led migration from monolith to microservices at a 200-person startup.",5.0),
    ("James Osei",     "james.osei@test.com",     "+1-404-555-0203","Atlanta",         "ai_outbound",
     "Backend Python developer 3 years, Django REST framework and PostgreSQL. CI/CD with GitHub Actions, Docker deployments.",3.0),
    ("Grace Kim",      "grace.kim@test.com",      "+1-415-555-0204","San Francisco",   "linkedin",
     "Backend engineer 4 years, Python Django, GraphQL, Celery, Redis. Team lead experience, mentored 2 juniors.",4.0),
    ("Lily Wang",      "lily.wang@test.com",      "+1-503-555-0205","Portland",        "careers_page",
     "Python engineer 2 years, built internal data pipelines with Airflow and FastAPI. Comfortable with async programming.",2.0),
    # iOS
    ("Aisha Kamara",   "aisha.kamara@test.com",   "+1-415-555-0101","San Francisco",   "linkedin",
     "Senior iOS engineer 6 years at Meta and Airbnb. Expert in SwiftUI, Combine, Core Data. Led iOS team for 3M-user fitness app. 4 apps on App Store.",6.0),
    ("Felix Nguyen",   "felix.nguyen@test.com",   "+1-408-555-0102","San Jose",        "referral",
     "iOS developer 5 years at Apple. Expert in SwiftUI, ARKit, Core ML. Published apps with 100K+ downloads.",5.0),
    ("Mia Torres",     "mia.torres@test.com",     "+1-650-555-0103","Austin",          "linkedin",
     "5 years iOS development at Uber Eats. Specialises in real-time features, MapKit, performance optimisation. SwiftUI, Combine, async/await.",5.0),
    # Data
    ("Nina Petrov",    "nina.petrov@test.com",    "+1-617-555-0301","Boston",          "linkedin",
     "Data scientist 5 years, NLP and recommendation systems. Built candidate-job matching model at LinkedIn, 87% precision. PyTorch, MLflow, AWS.",5.0),
    ("Carlos Mendez",  "carlos.mendez@test.com",  "+1-512-555-0302","Austin",          "referral",
     "ML engineer 4 years at Netflix. Recommendation and ranking models at scale. Python, TensorFlow, Spark, Databricks.",4.0),
    # PM
    ("Maya Chen",      "maya.chen@test.com",      "+1-415-555-0401","San Francisco",   "linkedin",
     "Product manager 6 years at HubSpot and Intercom. Led growth teams delivering 40% YoY ARR. SQL, Amplitude, Figma, A/B testing at scale.",6.0),
    ("Alex Johnson",   "alex.johnson@test.com",   "+1-212-555-0402","New York",        "referral",
     "PM 4 years in B2B SaaS, focus on onboarding and activation funnels. 0-to-1 launches, strong cross-functional leadership.",4.0),
    # Design
    ("Emma Laurent",   "emma.laurent@test.com",   "+1-310-555-0501","Los Angeles",     "linkedin",
     "Senior UX designer 5 years at Google and Figma. Expert in design systems, WCAG accessibility, large-scale design thinking.",5.0),
    ("Oliver Grant",   "oliver.grant@test.com",   "+1-212-555-0502","New York",        "job_board",
     "UX designer 4 years in enterprise software. Research-led design process, Figma expert, usability testing panels.",4.0),
    # Full Stack
    ("Chen Wei",       "chen.wei@test.com",       "+1-415-555-0801","San Francisco",   "linkedin",
     "Full-stack engineer 4 years, React/TypeScript frontend, Node.js/Express backend. PostgreSQL, GraphQL, Vercel deployments.",4.0),
    ("Isabel Morales", "isabel.morales@test.com", "+1-303-555-0802","Denver",          "referral",
     "Full-stack developer 3 years in early-stage startups. React, Node.js, Prisma ORM. Strong UX sensibility. Side projects 10K+ users.",3.0),
    # DevOps
    ("Kenji Tanaka",   "kenji.tanaka@test.com",   "+1-415-555-0601","Remote",          "linkedin",
     "DevOps engineer 5 years, AWS Certified Solutions Architect. Kubernetes cluster management, Terraform IaC, GitHub Actions, Datadog.",5.0),
    # Sales
    ("Marcus Johnson", "marcus.johnson@test.com", "+1-312-555-0701","Chicago",         "linkedin",
     "Enterprise sales executive 7 years, HR-tech and SaaS. Closed $4M ARR last year at Greenhouse. MEDDIC trained, Salesforce expert.",7.0),
    ("Sophie Klein",   "sophie.klein@test.com",   "+1-617-555-0702","Boston",          "referral",
     "Sales executive 5 years, mid-market B2B SaaS. Consistent 120% quota attainment, Outreach and Salesforce expert.",5.0),
]

cands_db = {}
for name, email, phone, loc, src, resume, exp in CANDIDATES:
    c = db.query(models.Candidate).filter(models.Candidate.email == email).first()
    if not c:
        c = models.Candidate(full_name=name, email=email, phone=phone, location=loc,
                             source=src, resume_text=resume, experience_years=exp,
                             created_at=ago(rng.randint(3, 45)))
        db.add(c); db.commit(); db.refresh(c)
    cands_db[email] = c

print(f"  ✔ Candidates: {len(cands_db)} ready")

# ── Applications — one clear set per job ───────────────────────────────────
APP_MAP = {
    "Senior Python Engineer": [
        ("tom.reyes@test.com",      "shortlisted", 89),
        ("sara.fischer@test.com",   "shortlisted", 85),
        ("james.osei@test.com",     "screening",   77),
        ("grace.kim@test.com",      "pending",     82),
        ("lily.wang@test.com",      "pending",     65),
    ],
    "Senior iOS Engineer": [
        ("aisha.kamara@test.com",   "screening",   91),
        ("felix.nguyen@test.com",   "shortlisted", 90),
        ("mia.torres@test.com",     "pending",     87),
    ],
    "Data Scientist — ML Platform": [
        ("nina.petrov@test.com",    "shortlisted", 93),
        ("carlos.mendez@test.com",  "shortlisted", 88),
    ],
    "Product Manager — Growth": [
        ("maya.chen@test.com",      "interview",   94),
        ("alex.johnson@test.com",   "shortlisted", 82),
    ],
    "Senior UX Designer": [
        ("emma.laurent@test.com",   "shortlisted", 91),
        ("oliver.grant@test.com",   "pending",     80),
    ],
    "Full Stack Engineer (React/Node)": [
        ("chen.wei@test.com",       "shortlisted", 88),
        ("isabel.morales@test.com", "screening",   80),
    ],
    "DevOps / Platform Engineer": [
        ("kenji.tanaka@test.com",   "interview",   90),
    ],
    "Enterprise Sales Executive": [
        ("marcus.johnson@test.com", "interview",   92),
        ("sophie.klein@test.com",   "shortlisted", 85),
    ],
}

apps_db = {}
for job_title, candidates in APP_MAP.items():
    job = job_by_title.get(job_title)
    if not job: continue
    for email, status, score in candidates:
        cand = cands_db.get(email)
        if not cand: continue
        existing = db.query(models.Application).filter(
            models.Application.job_id == job.id,
            models.Application.candidate_id == cand.id
        ).first()
        if existing:
            apps_db[(job.id, cand.id)] = existing
            continue
        app = models.Application(
            job_id=job.id, candidate_id=cand.id, status=status,
            match_score=score, skills_match=score-rng.randint(0,6),
            experience_match=score-rng.randint(0,5),
            applied_at=ago(rng.randint(1,12)),
        )
        db.add(app); db.commit(); db.refresh(app)
        apps_db[(job.id, cand.id)] = app

total_apps = db.query(models.Application).count()
print(f"  ✔ Applications: {total_apps} in DB")

# ── Screenings — for every candidate in screening/interview/shortlisted ────
SCREENING_DATA = {
    # (job_title, email): (status, overall, technical, recommendation, summary, strengths, weaknesses)
    ("Senior Python Engineer",  "tom.reyes@test.com"):
        ("completed",89,87,"pass",
         "Exceptional distributed systems and Python depth. Kafka and PostgreSQL expertise clearly demonstrated with real production examples.",
         ["Deep PostgreSQL performance tuning","Real 99.99% uptime delivery","Kafka stream processing expertise"],
         ["Limited Terraform IaC experience","Prefers monolith patterns for small services"]),
    ("Senior Python Engineer",  "james.osei@test.com"):
        ("in_progress",None,None,None,"Interview currently in progress",[],[]),
    ("Senior iOS Engineer",     "aisha.kamara@test.com"):
        ("completed",91,88,"pass",
         "Outstanding SwiftUI and Combine architecture knowledge. Real-world App Store submission experience validated.",
         ["Led 3M-user app iOS team","Expert Combine and async/await","App Store review process expertise"],
         ["Limited backend integration experience","No AR/VR experience"]),
    ("Product Manager — Growth","maya.chen@test.com"):
        ("completed",97,95,"pass",
         "Best PM candidate. Exceptional growth metrics, SQL and Amplitude skills confirmed with concrete examples.",
         ["Led 40% YoY ARR growth at HubSpot","Expert SQL and Amplitude","Outstanding cross-functional leadership"],
         ["May be overqualified","High equity expectations"]),
    ("Full Stack Engineer (React/Node)", "isabel.morales@test.com"):
        ("scheduled",None,None,None,"Invite sent, awaiting candidate",[],[]),
    ("DevOps / Platform Engineer","kenji.tanaka@test.com"):
        ("completed",93,92,"pass",
         "Exceptional Kubernetes and Terraform depth. AWS Certified Solutions Architect knowledge validated.",
         ["AWS CSA certified","Kubernetes production cluster management","Terraform IaC expert"],
         ["Limited GCP experience","No service mesh experience"]),
    ("Enterprise Sales Executive","marcus.johnson@test.com"):
        ("completed",95,88,"pass",
         "Elite enterprise seller. MEDDIC practised, $4M ARR track record validated with specific deal examples.",
         ["MEDDIC methodology mastered","HR-tech domain knowledge","Executive presence"],
         ["High base salary expectations","May prefer larger deal cycles"]),
}

scr_count = 0
for (job_title, email), (s_status, overall, technical, rec, summary, strengths, weaknesses) in SCREENING_DATA.items():
    job  = job_by_title.get(job_title)
    cand = cands_db.get(email)
    if not job or not cand: continue
    app = apps_db.get((job.id, cand.id))
    if not app: continue

    existing = db.query(models.Screening).filter(models.Screening.application_id == app.id).first()
    if existing: continue

    ai_eval = None
    if overall is not None:
        ai_eval = json.dumps({
            "summary": summary, "strengths": strengths, "weaknesses": weaknesses,
            "hiring_recommendation": "Recommended to Hire" if rec == "pass" else "Do Not Recommend",
            "overall_score": overall, "per_question": [],
        })

    completed_at = ago(rng.randint(1,5)) if s_status == "completed" else None
    scr = models.Screening(
        application_id=app.id, status=s_status,
        scheduled_at=ago(rng.randint(8,12)),
        started_at=ago(rng.randint(7,10)) if s_status in ("completed","in_progress") else None,
        completed_at=completed_at,
        overall_score=overall, technical_score=technical,
        communication_score=round(overall*0.95) if overall else None,
        cultural_fit_score=round(overall*0.90) if overall else None,
        recommendation=rec, ai_evaluation=ai_eval,
        source="auto", interview_session_id=str(uuid.uuid4()),
        invite_token=str(uuid.uuid4()),
        invite_sent_at=ago(rng.randint(9,13)),
        invite_expires_at=ago(-24),
        invite_used=(s_status in ("completed","in_progress")),
        created_at=ago(rng.randint(9,14)),
    )
    db.add(scr)
    if s_status == "completed" and rec == "pass":
        app.status = "shortlisted"
    db.commit()
    scr_count += 1

total_scr = db.query(models.Screening).count()
print(f"  ✔ Screenings: {scr_count} created  ({total_scr} total)")

# ── Activity logs ──────────────────────────────────────────────────────────
if db.query(models.ActivityLog).count() == 0:
    for ev in [
        (admin.id,     "user_created",           "user", admin.id),
        (recruiter.id, "user_created",           "user", recruiter.id),
        (recruiter.id, "job_created",            "job",  jobs_db[0].id),
        (recruiter.id, "screening_invite_sent",  "screening", 1),
        (recruiter.id, "application_shortlisted","application", 1),
    ]:
        db.add(models.ActivityLog(user_id=ev[0], action=ev[1], entity_type=ev[2], entity_id=ev[3]))
    db.commit()
    print(f"  ✔ Activity logs created")

db.close()

# ── Generate sample_resume.pdf ─────────────────────────────────────────────
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    pdf_path = Path(__file__).parent / "sample_resume.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, 730, "John Developer")
    c.setFont("Helvetica", 11)
    c.drawString(72, 712, "john.developer@email.com  |  +1-415-555-9999  |  San Francisco, CA")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, 688, "SUMMARY")
    c.setFont("Helvetica", 10)
    c.drawString(72, 672, "Senior Python Engineer with 5 years of experience building scalable backend systems.")
    c.drawString(72, 660, "Expert in FastAPI, PostgreSQL, Docker and AWS. Led teams of 3-6 engineers.")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, 636, "EXPERIENCE")
    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, 620, "Senior Backend Engineer — Stripe  (2021–Present)")
    c.setFont("Helvetica", 10)
    for i, line in enumerate([
        "• Built Python/FastAPI microservices processing 10M+ transactions daily",
        "• Optimised PostgreSQL queries reducing p99 latency from 400ms to 45ms",
        "• Led Docker/Kubernetes migration, achieving 99.99% uptime SLA",
        "• Mentored 3 junior engineers; conducted technical interviews",
    ]): c.drawString(80, 604 - i*14, line)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, 548, "Backend Engineer — Cloudflare  (2019–2021)")
    c.setFont("Helvetica", 10)
    for i, line in enumerate([
        "• Developed Python services for DDoS mitigation handling 2M req/s",
        "• Built Redis-backed rate limiting system used by 500K+ customers",
        "• Integrated Kafka event streaming for real-time analytics pipelines",
    ]): c.drawString(80, 532 - i*14, line)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, 490, "SKILLS")
    c.setFont("Helvetica", 10)
    c.drawString(72, 474, "Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS (EC2/RDS/Lambda),")
    c.drawString(72, 462, "Kafka, Terraform, GitHub Actions, REST APIs, GraphQL, SQL, Git")
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, 438, "EDUCATION")
    c.setFont("Helvetica", 10)
    c.drawString(72, 422, "B.S. Computer Science — University of California, Berkeley  (2019)")
    c.save()
    print(f"\n  ✔ sample_resume.pdf created at {pdf_path}")
except ImportError:
    print("\n  ℹ  reportlab not installed — creating text resume instead")
    txt_path = Path(__file__).parent / "sample_resume.txt"
    txt_path.write_text("""John Developer
john.developer@email.com | +1-415-555-9999 | San Francisco, CA

SUMMARY
Senior Python Engineer with 5 years experience building scalable backend systems.
Expert in FastAPI, PostgreSQL, Docker, and AWS. Led teams of 3-6 engineers.

EXPERIENCE
Senior Backend Engineer — Stripe (2021–Present)
- Built Python/FastAPI microservices processing 10M+ transactions daily
- Optimised PostgreSQL queries reducing p99 latency from 400ms to 45ms
- Led Docker/Kubernetes migration, achieving 99.99% uptime SLA
- Mentored 3 junior engineers

Backend Engineer — Cloudflare (2019–2021)
- Developed Python services for DDoS mitigation handling 2M req/s
- Built Redis-backed rate limiting system
- Integrated Kafka event streaming for real-time analytics

SKILLS
Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes,
AWS (EC2/RDS/Lambda), Kafka, Terraform, GitHub Actions, REST APIs

EDUCATION
B.S. Computer Science — UC Berkeley (2019)
""")
    print(f"  ✔ sample_resume.txt created at {txt_path}")

print("""
═══════════════════════════════════════════════════════
  SEED COMPLETE!

  LOGIN CREDENTIALS
  ─────────────────
  Admin:     admin@talentbridge.ai     / Admin@123
  Recruiter: recruiter@talentbridge.ai / Recruiter@123

  E2E TEST FLOW
  ─────────────
  1.  Login → Dashboard shows live metrics
  2.  Jobs  → See 8 active jobs, "Senior iOS" marked Urgent
  3.  Go to http://localhost:5173/browse-jobs (no login)
  4.  Click "Senior Python Engineer" → View & Apply
  5.  Fill form + upload sample_resume.pdf → Submit
  6.  Back in recruiter → Applications → Python Engineer card
      → New application appears with AI match score
  7.  Click ✓ to shortlist, then ✨ to send screening invite
  8.  Screenings → Python Engineer accordion shows all candidates
      → Filter by "Completed" to see scored results
  9.  Notifications bell → completions appear with scores
 10.  Candidates → "View Profile" → full history + resume
═══════════════════════════════════════════════════════
""")
