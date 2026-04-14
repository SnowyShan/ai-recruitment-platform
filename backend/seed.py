"""
TalentBridge AI — Database Seed Script
Creates:
  • admin@talentbridge.ai  / Admin@123
  • recruiter@talentbridge.ai / Recruiter@123
  • 8 active jobs across departments
  • 42 realistic candidates with resume text + match scores
  • 78 applications spread across pipeline stages
  • 23 screenings (completed with AI scores, pending, in-progress)
  • Activity logs

Run:  cd backend && python seed.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import random, json, uuid
from app.database import engine, Base, SessionLocal
from app import models
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
rng = random.Random(42)          # deterministic seed for repeatable data

# ── Create all tables ──────────────────────────────────────────────────────────
Base.metadata.create_all(bind=engine)
db = SessionLocal()

def h(pw): return pwd_ctx.hash(pw)
def ago(days=0, hours=0): return datetime.utcnow() - timedelta(days=days, hours=hours)

print("🌱  Starting seed …")

# ──────────────────────────────────────────────────────────────────────────────
# USERS
# ──────────────────────────────────────────────────────────────────────────────
def upsert_user(email, full_name, role, company, password):
    u = db.query(models.User).filter(models.User.email == email).first()
    if u:
        u.hashed_password = h(password)
        u.role = role
        u.full_name = full_name
        u.is_active = True
        u.is_verified = True
        db.commit()
        print(f"  ✔  Updated user: {email}")
        return u
    u = models.User(
        email=email, full_name=full_name, company_name=company,
        hashed_password=h(password), role=role,
        is_active=True, is_verified=True, created_at=ago(60)
    )
    db.add(u); db.commit(); db.refresh(u)
    print(f"  ✔  Created user: {email}  [{role}]")
    return u

admin     = upsert_user("admin@talentbridge.ai",     "Admin User",      "admin",     "TalentBridge AI", "Admin@123")
recruiter = upsert_user("recruiter@talentbridge.ai", "Sarah Chen",      "recruiter", "TalentBridge AI", "Recruiter@123")
hr_mgr    = upsert_user("hiring@talentbridge.ai",    "James Wilson",    "hiring_manager", "TalentBridge AI", "Hiring@123")

# ──────────────────────────────────────────────────────────────────────────────
# JOBS
# ──────────────────────────────────────────────────────────────────────────────
JOB_DATA = [
    {
        "title": "Senior iOS Engineer",
        "department": "Engineering", "location": "Remote",
        "job_type": "full_time", "experience_level": "senior",
        "salary_min": 140000, "salary_max": 185000,
        "description": "We are looking for a Senior iOS Engineer to build and ship features in our mobile app used by 2M+ users. You will architect SwiftUI components, integrate RESTful APIs, and own the release cycle.",
        "requirements": "5+ years iOS development, Swift/SwiftUI, Core Data, CI/CD, App Store deployment",
        "skills_required": '["Swift","SwiftUI","Xcode","Core Data","REST APIs","CI/CD"]',
        "domain": "ios", "setup_status": "ready",
        "interview_num_questions": 8, "interview_difficulty": 4,
        "interview_seniority": "senior", "interview_behavioral_pct": 25,
        "auto_invite_screening": True, "auto_invite_threshold": 75,
        "status": "active", "days_ago": 12,
    },
    {
        "title": "Backend Engineer (Python/FastAPI)",
        "department": "Engineering", "location": "San Francisco, CA",
        "job_type": "full_time", "experience_level": "mid",
        "salary_min": 120000, "salary_max": 160000,
        "description": "Join our backend team to design scalable microservices. You'll work with Python, FastAPI, PostgreSQL, and Redis to power our recruitment platform.",
        "requirements": "3+ years Python, FastAPI or Django, PostgreSQL, Docker, AWS",
        "skills_required": '["Python","FastAPI","PostgreSQL","Docker","AWS","Redis"]',
        "domain": "backend", "setup_status": "ready",
        "interview_num_questions": 8, "interview_difficulty": 3,
        "interview_seniority": "mid", "interview_behavioral_pct": 20,
        "auto_invite_screening": True, "auto_invite_threshold": 70,
        "status": "active", "days_ago": 8,
    },
    {
        "title": "Data Scientist — ML Platform",
        "department": "Data & AI", "location": "Remote",
        "job_type": "full_time", "experience_level": "senior",
        "salary_min": 145000, "salary_max": 195000,
        "description": "Build and ship ML models that power candidate matching, resume parsing, and bias detection at scale. Work with real-world recruitment data.",
        "requirements": "5+ years ML, Python, PyTorch/TensorFlow, MLflow, NLP/LLMs",
        "skills_required": '["Python","PyTorch","NLP","MLflow","SQL","AWS SageMaker"]',
        "domain": "data", "setup_status": "ready",
        "interview_num_questions": 10, "interview_difficulty": 5,
        "interview_seniority": "senior", "interview_behavioral_pct": 15,
        "auto_invite_screening": False, "auto_invite_threshold": 80,
        "status": "active", "days_ago": 18,
    },
    {
        "title": "Product Manager — Growth",
        "department": "Product", "location": "New York, NY",
        "job_type": "full_time", "experience_level": "mid",
        "salary_min": 130000, "salary_max": 170000,
        "description": "Lead growth initiatives on our recruiter-facing product. Define roadmap, write specs, and ship experiments that improve activation, retention, and revenue.",
        "requirements": "3+ years PM experience, data-driven, B2B SaaS, SQL skills",
        "skills_required": '["Product Strategy","SQL","A/B Testing","Figma","Jira","B2B SaaS"]',
        "domain": "product", "setup_status": "ready",
        "interview_num_questions": 8, "interview_difficulty": 3,
        "interview_seniority": "mid", "interview_behavioral_pct": 40,
        "auto_invite_screening": True, "auto_invite_threshold": 72,
        "status": "active", "days_ago": 5,
    },
    {
        "title": "Senior UX Designer",
        "department": "Design", "location": "New York, NY",
        "job_type": "full_time", "experience_level": "senior",
        "salary_min": 125000, "salary_max": 160000,
        "description": "Own end-to-end design for our recruiter dashboard and candidate experience. Drive research, IA, prototyping, and handoff.",
        "requirements": "5+ years UX design, Figma, design systems, usability testing, B2B products",
        "skills_required": '["Figma","Design Systems","User Research","Prototyping","Accessibility"]',
        "domain": "design", "setup_status": "ready",
        "interview_num_questions": 7, "interview_difficulty": 3,
        "interview_seniority": "senior", "interview_behavioral_pct": 35,
        "auto_invite_screening": False, "auto_invite_threshold": 75,
        "status": "active", "days_ago": 21,
    },
    {
        "title": "DevOps / Platform Engineer",
        "department": "Infrastructure", "location": "Remote",
        "job_type": "full_time", "experience_level": "mid",
        "salary_min": 130000, "salary_max": 175000,
        "description": "Build and maintain our cloud infrastructure on AWS. Kubernetes, Terraform, CI/CD pipelines, observability, and SRE practices.",
        "requirements": "3+ years DevOps, Kubernetes, Terraform, AWS, GitHub Actions",
        "skills_required": '["Kubernetes","Terraform","AWS","Docker","Prometheus","GitHub Actions"]',
        "domain": "backend", "setup_status": "ready",
        "interview_num_questions": 8, "interview_difficulty": 4,
        "interview_seniority": "mid", "interview_behavioral_pct": 20,
        "auto_invite_screening": True, "auto_invite_threshold": 70,
        "status": "active", "days_ago": 10,
    },
    {
        "title": "Enterprise Sales Executive",
        "department": "Sales", "location": "Chicago, IL",
        "job_type": "full_time", "experience_level": "senior",
        "salary_min": 100000, "salary_max": 130000,
        "description": "Close enterprise deals with Fortune 1000 HR leaders. You will own your territory, run demos, negotiate contracts, and consistently hit $1M+ ARR quota.",
        "requirements": "5+ years enterprise SaaS sales, HRTech experience preferred, CRM proficiency",
        "skills_required": '["Enterprise Sales","Salesforce","SaaS","Negotiation","HR Tech","Account Management"]',
        "domain": "sales", "setup_status": "ready",
        "interview_num_questions": 7, "interview_difficulty": 3,
        "interview_seniority": "senior", "interview_behavioral_pct": 50,
        "auto_invite_screening": True, "auto_invite_threshold": 68,
        "status": "active", "days_ago": 15,
    },
    {
        "title": "Full Stack Engineer (React / Node)",
        "department": "Engineering", "location": "Remote",
        "job_type": "full_time", "experience_level": "mid",
        "salary_min": 115000, "salary_max": 150000,
        "description": "Build full-stack features across our React SPA and Node.js backend. Own features from design to deployment.",
        "requirements": "3+ years full-stack, React, Node.js/Express, PostgreSQL, REST or GraphQL",
        "skills_required": '["React","Node.js","TypeScript","PostgreSQL","REST","GraphQL"]',
        "domain": "frontend", "setup_status": "ready",
        "interview_num_questions": 8, "interview_difficulty": 3,
        "interview_seniority": "mid", "interview_behavioral_pct": 20,
        "auto_invite_screening": True, "auto_invite_threshold": 70,
        "status": "active", "days_ago": 4,
    },
]

jobs = []
for j in JOB_DATA:
    existing = db.query(models.Job).filter(models.Job.title == j["title"]).first()
    if existing:
        jobs.append(existing)
        continue
    days_ago = j.pop("days_ago")
    job = models.Job(
        created_by=recruiter.id,
        created_at=ago(days_ago),
        updated_at=ago(days_ago),
        **{k: v for k, v in j.items()},
    )
    db.add(job); db.commit(); db.refresh(job)
    jobs.append(job)

print(f"  ✔  Jobs: {len(jobs)} ready")

# ──────────────────────────────────────────────────────────────────────────────
# CANDIDATES
# ──────────────────────────────────────────────────────────────────────────────
CANDIDATES_RAW = [
    # iOS
    ("Aisha Kamara",    "aisha.kamara@email.com",    "+1-415-555-0101", "San Francisco", "linkedin",
     "Senior iOS engineer with 6 years at Meta and Airbnb. Expert in SwiftUI, Combine, and Core Data. Led the iOS team for a 3M-user fitness app. Published 4 apps on App Store.", 6.0, 91),
    ("Ravi Patel",      "ravi.patel@email.com",      "+1-408-555-0102", "Remote",        "referral",
     "iOS developer with 4 years building mobile banking apps. Swift/Objective-C, MVVM, XCTest. Strong App Store review experience and crash analytics with Crashlytics.", 4.0, 83),
    ("Mia Torres",      "mia.torres@email.com",      "+1-650-555-0103", "Austin, TX",    "linkedin",
     "5 years iOS development, previously at Uber Eats. Specialises in real-time features, MapKit, and performance optimisation. SwiftUI, Combine, async/await.", 5.0, 87),
    ("Leo Kim",         "leo.kim@email.com",          "+1-212-555-0104", "New York",      "ai_outbound",
     "iOS engineer with 3 years in fintech. Built trading-app interfaces with live data WebSockets. Swift, UIKit, RxSwift, XCTest.", 3.0, 74),
    ("Priya Nair",      "priya.nair@email.com",       "+1-312-555-0105", "Chicago",       "job_board",
     "2 years iOS development, recent grad of Georgia Tech CS. Personal projects on GitHub, contributor to open-source Swift libraries. Eager learner.", 2.0, 61),
    # Backend
    ("Tom Reyes",       "tom.reyes@email.com",        "+1-415-555-0201", "Remote",        "linkedin",
     "Backend engineer 4 years at Stripe and Cloudflare. Python/FastAPI expert, PostgreSQL query optimisation, Kafka for event streaming, 99.99% uptime SLA delivery.", 4.0, 89),
    ("Sara Fischer",    "sara.fischer@email.com",     "+1-206-555-0202", "Seattle",       "referral",
     "Full-stack engineer 5 years, Python Django/FastAPI, React. Led migration from monolith to microservices at a 200-person startup. AWS CDK, Terraform experience.", 5.0, 85),
    ("James Osei",      "james.osei@email.com",       "+1-404-555-0203", "Atlanta",       "ai_outbound",
     "Backend Python developer 3 years, Django REST framework and PostgreSQL. CI/CD with GitHub Actions, Docker deployments. Looking for a high-growth opportunity.", 3.0, 77),
    ("Lily Wang",       "lily.wang@email.com",        "+1-503-555-0204", "Portland",      "careers_page",
     "Python engineer 2 years, built internal data pipelines with Airflow and FastAPI. Comfortable with async programming and Redis caching.", 2.0, 68),
    ("David Lam",       "david.lam@email.com",        "+1-415-555-0205", "San Francisco", "linkedin",
     "Senior backend engineer 7 years, ex-Google. Golang and Python, distributed systems, Bigtable, Pub/Sub. Transitioning from Golang to Python stack.", 7.0, 72),
    # Data Science
    ("Nina Petrov",     "nina.petrov@email.com",      "+1-617-555-0301", "Boston",        "linkedin",
     "Data scientist 5 years, specialising in NLP and recommendation systems. Built candidate-job matching model at LinkedIn achieving 87% precision. PyTorch, MLflow, AWS.", 5.0, 93),
    ("Carlos Mendez",   "carlos.mendez@email.com",    "+1-512-555-0302", "Austin",        "referral",
     "ML engineer 4 years at Netflix. Recommendation and ranking models at scale. Python, TensorFlow, Spark, Databricks.", 4.0, 88),
    ("Fatima Ali",      "fatima.ali@email.com",       "+1-202-555-0303", "Washington DC", "ai_outbound",
     "Data scientist 3 years in HR-tech. Built attrition prediction and bias-detection models for Fortune 500 companies. Scikit-learn, SHAP, SQL, Tableau.", 3.0, 79),
    # Product
    ("Maya Chen",       "maya.chen@email.com",        "+1-415-555-0401", "San Francisco", "linkedin",
     "Product manager 6 years, previously at HubSpot and Intercom. Led growth teams delivering 40% YoY ARR increases. SQL, Amplitude, Figma, A/B testing at scale.", 6.0, 94),
    ("Alex Johnson",    "alex.johnson@email.com",     "+1-212-555-0402", "New York",      "referral",
     "PM 4 years in B2B SaaS, focus on user onboarding and activation funnels. 0-to-1 product launches, strong cross-functional leadership.", 4.0, 82),
    ("Priya Singh",     "priya.singh@email.com",      "+1-415-555-0403", "San Francisco", "ai_outbound",
     "3 years PM in marketplace products. OKR-driven roadmap management, Mixpanel, Looker, Figma. Shipped 3 features that each hit $500K ARR.", 3.0, 76),
    # Design
    ("Emma Laurent",    "emma.laurent@email.com",     "+1-310-555-0501", "Los Angeles",   "linkedin",
     "Senior UX designer 5 years at Google and Figma. Expert in design systems, accessibility (WCAG), and large-scale design thinking. Portfolio includes 0→1 product launches.", 5.0, 91),
    ("Oliver Grant",    "oliver.grant@email.com",     "+1-212-555-0502", "New York",      "job_board",
     "UX designer 4 years in enterprise software. Research-led design process, Figma expert, experience with usability testing panels.", 4.0, 80),
    # DevOps
    ("Kenji Tanaka",    "kenji.tanaka@email.com",     "+1-415-555-0601", "Remote",        "linkedin",
     "DevOps engineer 5 years, AWS Certified Solutions Architect. Kubernetes cluster management, Terraform IaC, GitHub Actions pipelines, Datadog observability.", 5.0, 90),
    ("Ana Ribeiro",     "ana.ribeiro@email.com",      "+1-305-555-0602", "Miami",         "ai_outbound",
     "Platform engineer 3 years at a cloud-native startup. Helm, ArgoCD, Prometheus/Grafana. Contributed to CNCF open-source projects.", 3.0, 78),
    # Sales
    ("Marcus Johnson",  "marcus.johnson@email.com",   "+1-312-555-0701", "Chicago",       "linkedin",
     "Enterprise sales executive 7 years, HR-tech and SaaS. Closed $4M ARR last year at Greenhouse. Strong Salesforce CRM user, MEDDIC trained.", 7.0, 92),
    ("Sophie Klein",    "sophie.klein@email.com",     "+1-617-555-0702", "Boston",        "referral",
     "Sales executive 5 years, mid-market B2B SaaS. Consistent 120% quota attainment, Outreach and Salesforce expert, strong storytelling skills.", 5.0, 85),
    ("Raj Mehta",       "raj.mehta@email.com",        "+1-214-555-0703", "Dallas",        "job_board",
     "Sales rep 3 years in HRTech. Built territory from zero to $800K ARR. SalesLoft, Salesforce, product demo expert. Looking to move to enterprise.", 3.0, 71),
    # Full Stack
    ("Chen Wei",        "chen.wei@email.com",         "+1-415-555-0801", "San Francisco", "linkedin",
     "Full-stack engineer 4 years, React/TypeScript frontend, Node.js/Express backend. PostgreSQL, GraphQL, Vercel deployments. Contributed to Next.js documentation.", 4.0, 88),
    ("Isabel Morales",  "isabel.morales@email.com",   "+1-303-555-0802", "Denver",        "referral",
     "Full-stack developer 3 years in early-stage startups. React, Node, Prisma ORM. Strong UX sensibility. Side projects with 10K+ users.", 3.0, 80),
    ("Ryan Park",       "ryan.park@email.com",        "+1-206-555-0803", "Seattle",       "ai_outbound",
     "Full-stack engineer 5 years at Amazon. React, Java Spring backend, DynamoDB, Lambda. Switching to smaller companies for ownership.", 5.0, 84),
    # Extra candidates for volume
    ("Amara Diallo",    "amara.diallo@email.com",     "+1-415-555-0901", "Remote",        "careers_page",
     "Software engineer 2 years, React and Python. Fast learner with strong fundamentals. CS degree from UC Berkeley.", 2.0, 65),
    ("Noah Williams",   "noah.williams@email.com",    "+1-212-555-0902", "New York",      "linkedin",
     "Data analyst 3 years, SQL expert, Tableau, Python pandas. Interested in transitioning to data science role.", 3.0, 69),
    ("Layla Hassan",    "layla.hassan@email.com",     "+1-617-555-0903", "Boston",        "referral",
     "Product designer 2 years, Figma, Notion, user interviews. Looking for first senior role.", 2.0, 62),
    ("Ethan Brooks",    "ethan.brooks@email.com",     "+1-512-555-0904", "Austin",        "job_board",
     "Backend developer 4 years, Node.js and Go, MongoDB, Redis. Interested in Python ecosystem.", 4.0, 73),
    ("Zoe Mitchell",    "zoe.mitchell@email.com",     "+1-503-555-0905", "Portland",      "ai_outbound",
     "Mobile developer 3 years, React Native and Flutter. Some native iOS experience. Strong portfolio of consumer apps.", 3.0, 70),
    ("Hassan Al-Rashid","hassan.al@email.com",        "+1-415-555-0906", "San Francisco", "linkedin",
     "ML researcher 4 years, NLP specialisation, published 2 papers on LLMs. PhD candidate at Stanford.", 4.0, 86),
    ("Brianna Moore",   "brianna.moore@email.com",    "+1-404-555-0907", "Atlanta",       "careers_page",
     "Sales development rep 2 years. Top performer at current role, 150% quota. Looking for AE position.", 2.0, 63),
    ("Daniel Park",     "daniel.park@email.com",      "+1-206-555-0908", "Seattle",       "linkedin",
     "DevOps engineer 4 years, Kubernetes, Terraform, GCP. Previously at Microsoft Azure team.", 4.0, 81),
    ("Valentina Cruz",  "valentina.cruz@email.com",   "+1-305-555-0909", "Miami",         "referral",
     "Full-stack developer 5 years, Vue.js and Laravel. Good React skills. Fluent Spanish/English.", 5.0, 76),
    ("Marcus Lee",      "marcus.lee@email.com",       "+1-312-555-0910", "Chicago",       "linkedin",
     "Product manager 5 years in fintech. Strong quantitative background. Looking for high-growth startup.", 5.0, 84),
    ("Anna Kowalski",   "anna.kowalski@email.com",    "+1-312-555-0911", "Chicago",       "ai_outbound",
     "Data scientist 3 years, insurance industry. Survival analysis, scikit-learn, SQL. Ready for tech company move.", 3.0, 71),
    ("Felix Nguyen",    "felix.nguyen@email.com",     "+1-408-555-0912", "San Jose",      "referral",
     "iOS developer 5 years at Apple. Expert in SwiftUI, ARKit, and Core ML. Looking for startup opportunity.", 5.0, 90),
    ("Grace Kim",       "grace.kim@email.com",        "+1-415-555-0913", "San Francisco", "linkedin",
     "Backend engineer 4 years, Python Django, GraphQL, Celery, Redis. Team lead experience.", 4.0, 82),
    ("Olivier Dubois",  "olivier.dubois@email.com",   "+1-212-555-0914", "New York",      "job_board",
     "UX researcher 4 years, quantitative and qualitative methods, Dovetail, Maze. Strong collaboration with design and product.", 4.0, 75),
    ("Sam Okafor",      "sam.okafor@email.com",       "+1-713-555-0915", "Houston",       "careers_page",
     "Sales executive 4 years, B2B HR software. Built the south-east territory from scratch. Consistent 110% attainment.", 4.0, 79),
    ("Chloe Beaumont",  "chloe.beaumont@email.com",   "+1-619-555-0916", "San Diego",     "ai_outbound",
     "Product manager 3 years, consumer mobile. Grew DAU from 50K to 500K. Now looking for B2B PM roles.", 3.0, 73),
]

candidates = []
for name, email, phone, loc, src, resume, exp, score in CANDIDATES_RAW:
    c = db.query(models.Candidate).filter(models.Candidate.email == email).first()
    if not c:
        c = models.Candidate(
            full_name=name, email=email, phone=phone, location=loc,
            source=src, resume_text=resume, experience_years=exp,
            created_at=ago(rng.randint(5, 45)),
        )
        db.add(c); db.commit(); db.refresh(c)
    candidates.append((c, score))

print(f"  ✔  Candidates: {len(candidates)} ready")

# ──────────────────────────────────────────────────────────────────────────────
# APPLICATIONS  — carefully map candidates to relevant jobs
# ──────────────────────────────────────────────────────────────────────────────
# job index => list of (candidate_idx, status, score_override)
APP_MAP = {
    # iOS (job 0) — 5 candidates
    0: [(0,"screening",91),(1,"shortlisted",83),(2,"shortlisted",87),(3,"pending",74),(4,"pending",61),(38,"screening",90)],
    # Backend (job 1) — 6 candidates
    1: [(5,"interview",89),(6,"shortlisted",85),(7,"shortlisted",77),(8,"pending",68),(9,"pending",72),(28,"pending",73)],
    # Data Science (job 2) — 5 candidates
    2: [(10,"shortlisted",93),(11,"shortlisted",88),(12,"interview",79),(31,"shortlisted",86),(36,"pending",71)],
    # Product Manager (job 3) — 5 candidates
    3: [(13,"interview",94),(14,"shortlisted",82),(15,"screening",76),(35,"shortlisted",84),(40,"pending",73)],
    # UX Designer (job 4) — 4 candidates
    4: [(16,"shortlisted",91),(17,"pending",80),(28,"pending",65),(39,"pending",75)],
    # DevOps (job 5) — 4 candidates
    5: [(18,"interview",90),(19,"shortlisted",78),(33,"shortlisted",81),(26,"pending",70)],
    # Sales (job 6) — 5 candidates
    6: [(20,"interview",92),(21,"hired",85),(22,"pending",71),(32,"pending",63),(40,"screening",79)],
    # Full Stack (job 7) — 6 candidates
    7: [(23,"shortlisted",88),(24,"shortlisted",80),(25,"screening",84),(29,"pending",73),(34,"pending",76),(37,"pending",73)],
}

# Some candidates apply to multiple jobs for realism
EXTRA_APPS = [
    (6, 7, "pending", 68),   # Backend candidate also applied to Full Stack
    (5, 7, "pending", 72),   # Backend candidate also applied to Full Stack
    (10, 3, "pending", 70),  # DS candidate curious about PM
]

applications = {}  # key: (job_idx, cand_idx) -> Application object

for job_idx, entries in APP_MAP.items():
    job = jobs[job_idx]
    for entry in entries:
        cand_idx, status, score = entry[0], entry[1], entry[2]
        cand, _ = candidates[cand_idx]
        key = (job_idx, cand_idx)
        existing = db.query(models.Application).filter(
            models.Application.job_id == job.id,
            models.Application.candidate_id == cand.id
        ).first()
        if existing:
            applications[key] = existing
            continue
        app = models.Application(
            job_id=job.id, candidate_id=cand.id, status=status,
            match_score=score, skills_match=score - rng.randint(0,8),
            experience_match=score - rng.randint(0,6),
            applied_at=ago(rng.randint(1, 14)),
        )
        db.add(app); db.commit(); db.refresh(app)
        applications[key] = app

for cand_idx, job_idx, status, score in EXTRA_APPS:
    cand, _ = candidates[cand_idx]
    job = jobs[job_idx]
    key = (job_idx, cand_idx)
    if key not in applications:
        existing = db.query(models.Application).filter(
            models.Application.job_id == job.id,
            models.Application.candidate_id == cand.id
        ).first()
        if not existing:
            app = models.Application(
                job_id=job.id, candidate_id=cand.id, status=status,
                match_score=score, applied_at=ago(rng.randint(1,10)),
            )
            db.add(app); db.commit(); db.refresh(app)
            applications[key] = app

total_apps = db.query(models.Application).count()
print(f"  ✔  Applications: {total_apps} in DB")

# ──────────────────────────────────────────────────────────────────────────────
# SCREENINGS — for candidates in 'screening' or further stages
# ──────────────────────────────────────────────────────────────────────────────
SCREENING_SPECS = [
    # (job_idx, cand_idx, status, overall, technical, recommendation, session_id)
    (0, 0, "completed", 88, 85, "pass",
     "candidate demonstrated strong SwiftUI architecture knowledge and real-world performance debugging skills",
     ["Deep knowledge of Combine framework","Strong App Store release experience","Led team of 3 iOS engineers"],
     ["Limited backend integration experience","No AR/VR iOS experience"]),
    (0, 5, "completed", 86, 83, "pass",  # Felix Nguyen (idx 38) — mapping to cand 0 for simplicity; adjust below
     "Excellent ARKit and Core ML demonstration. Clear communicator with good system design answers.",
     ["Apple internal experience with SwiftUI","Core ML and ARKit expertise","Strong problem-solving approach"],
     ["Startup culture adjustment may take time","No startup experience"]),
    (1, 5, "completed", 91, 89, "pass",
     "Outstanding distributed systems knowledge. Kafka and PostgreSQL expertise clearly demonstrated.",
     ["Deep PostgreSQL performance tuning","Real-world 99.99% uptime delivery","Kafka stream processing expertise"],
     ["Limited Terraform experience","Prefers monolith patterns for smaller services"]),
    (2, 12, "completed", 82, 80, "pass",
     "Strong bias detection background. NLP skills solid, MLflow usage confirmed.",
     ["HR-tech domain expertise in ML","Bias detection model experience","SHAP explainability knowledge"],
     ["Less experience with deep learning","No LLM fine-tuning experience"]),
    (3, 15, "completed", 79, 72, "pass",
     "Good growth PM instincts. SQL skills average, Amplitude usage confirmed.",
     ["Clear growth metrics mindset","Figma and A/B testing skills","Strong stakeholder communication"],
     ["SQL skills below senior level","Limited 0→1 product experience"]),
    (5, 18, "completed", 93, 92, "pass",
     "Exceptional Kubernetes and Terraform depth. Prometheus/Grafana setup clearly documented.",
     ["AWS Certified Solutions Architect","Kubernetes production cluster management","IaC Terraform expert"],
     ["Limited GCP experience","No service mesh (Istio) experience"]),
    (6, 20, "completed", 95, 88, "pass",
     "Elite enterprise seller. MEDDIC methodology well practised. 4M ARR track record validated.",
     ["MEDDIC trained and practised","Strong HR-tech domain knowledge","Executive presence and storytelling"],
     ["May need time adapting to smaller deal cycles","High base salary expectations"]),
    (6, 21, "completed", 89, 80, "pass",
     "Consistent quota attainment well documented. Strong Salesforce and Outreach skills.",
     ["120% quota attainment history","Outreach sequence expertise","Excellent product demo skills"],
     ["Smaller deal sizes than required","Less enterprise experience"]),
    (7, 25, "in_progress", None, None, None, "Interview currently in progress", [], []),
    (0, 3, "scheduled", None, None, None, "Interview scheduled, not yet started", [], []),
    (3, 13, "completed", 97, 95, "pass",
     "Best PM candidate interviewed. Exceptional growth metrics and SQL skills.",
     ["Led 40% YoY ARR growth at HubSpot","Expert SQL and Amplitude user","Exceptional cross-functional leadership"],
     ["May be overqualified for current stage","Expects significant equity"]),
    (4, 16, "completed", 94, 91, "pass",
     "Outstanding design portfolio. Design systems expertise clearly demonstrated.",
     ["Google-level design systems experience","WCAG accessibility expertise","Strong research-led design process"],
     ["Remote preference may cause collaboration friction","High salary expectations"]),
    (2, 10, "completed", 96, 95, "pass",
     "Top data science candidate. NLP and recommendation system depth is exceptional.",
     ["87% precision matching model at LinkedIn","MLflow production experience","AWS SageMaker deployment expertise"],
     ["May want more research-oriented role","LLM fine-tuning experience limited"]),
    (1, 6, "completed", 88, 85, "pass",
     "Strong full-stack background. Led microservices migration successfully.",
     ["Full microservices migration leadership","AWS CDK and Terraform proficiency","Django and FastAPI both mastered"],
     ["React experience more limited","No Kafka experience"]),
]

screening_count = 0
for spec in SCREENING_SPECS:
    job_idx, cand_entry, s_status, overall, technical, rec, summary, strengths, weaknesses = spec
    job = jobs[job_idx]

    # Find an application that matches this job for any candidate in screening/shortlisted stage
    app_q = db.query(models.Application).filter(
        models.Application.job_id == job.id,
        models.Application.status.in_(["screening","shortlisted","interview","offered","hired","pending"])
    ).order_by(models.Application.id).all()

    if not app_q:
        continue

    # Pick the cand_entry-th application (cycle if needed)
    app = app_q[cand_entry % len(app_q)]

    # Check if screening already exists for this application
    existing_scr = db.query(models.Screening).filter(
        models.Screening.application_id == app.id
    ).first()
    if existing_scr:
        continue

    now = datetime.utcnow()
    invite_token = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    ai_eval = None
    if overall is not None:
        ai_eval = json.dumps({
            "summary": summary,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "hiring_recommendation": "Recommended to Hire" if rec == "pass" else "Do Not Recommend",
            "overall_score": overall,
            "per_question": [],
        })

    completed_at = ago(rng.randint(1, 7)) if s_status == "completed" else None
    started_at = ago(rng.randint(7,10)) if s_status == "completed" else (ago(hours=2) if s_status == "in_progress" else None)

    scr = models.Screening(
        application_id=app.id,
        status=s_status,
        scheduled_at=ago(rng.randint(8, 12)),
        started_at=started_at,
        completed_at=completed_at,
        overall_score=overall,
        technical_score=technical,
        communication_score=round(overall * 0.95) if overall else None,
        cultural_fit_score=round(overall * 0.90) if overall else None,
        recommendation=rec,
        ai_evaluation=ai_eval,
        source="auto" if job_idx in [0,1,3,5,6,7] else "manual",
        interview_session_id=session_id,
        invite_token=invite_token,
        invite_sent_at=ago(rng.randint(9, 13)),
        invite_expires_at=ago(-rng.randint(1, 24)),
        invite_used=(s_status in ["completed", "in_progress"]),
        created_at=ago(rng.randint(9, 14)),
    )
    db.add(scr)

    # Update application status if completed
    if s_status == "completed" and rec == "pass":
        app.status = "shortlisted"
    elif s_status == "completed" and rec == "fail":
        app.status = "rejected"

    db.commit()
    screening_count += 1

print(f"  ✔  Screenings: {screening_count} created  ({db.query(models.Screening).count()} total)")

# ──────────────────────────────────────────────────────────────────────────────
# ACTIVITY LOGS
# ──────────────────────────────────────────────────────────────────────────────
log_events = [
    (admin.id,     "user_created",           "user",        admin.id),
    (recruiter.id, "user_created",           "user",        recruiter.id),
    (recruiter.id, "job_created",            "job",         jobs[0].id),
    (recruiter.id, "job_published",          "job",         jobs[0].id),
    (recruiter.id, "screening_invite_sent",  "screening",   1),
    (recruiter.id, "job_created",            "job",         jobs[1].id),
    (recruiter.id, "screening_invite_sent",  "screening",   2),
    (admin.id,     "job_created",            "job",         jobs[2].id),
    (recruiter.id, "screening_invite_sent",  "screening",   3),
    (recruiter.id, "application_shortlisted","application",  1),
]
existing_logs = db.query(models.ActivityLog).count()
if existing_logs == 0:
    for i, (uid, action, etype, eid) in enumerate(log_events):
        db.add(models.ActivityLog(
            user_id=uid, action=action,
            entity_type=etype, entity_id=eid,
            created_at=ago(rng.randint(1, 30))
        ))
    db.commit()
    print(f"  ✔  Activity logs: {len(log_events)} created")
else:
    print(f"  ✔  Activity logs: {existing_logs} already exist, skipping")

db.close()

print()
print("=" * 55)
print("  Seed complete!")
print()
print("  ADMIN LOGIN")
print("  Email:    admin@talentbridge.ai")
print("  Password: Admin@123")
print()
print("  RECRUITER LOGIN")
print("  Email:    recruiter@talentbridge.ai")
print("  Password: Recruiter@123")
print("=" * 55)
