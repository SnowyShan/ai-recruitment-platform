"""
Gmail SMTP email utility for TalentBridge.
Configure GMAIL_USER and GMAIL_APP_PASSWORD in .env
Use a Gmail App Password (not your regular password):
  Google Account → Security → 2-Step Verification → App passwords
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
INTERVIEW_MODULE_URL = os.getenv("INTERVIEW_MODULE_URL", "http://localhost:5174")


def send_screening_invite(
    candidate_name: str,
    candidate_email: str,
    job_title: str,
    company_name: str,
    session_id: str,
    invite_token: str,
    expires_hours: int = 48,
) -> bool:
    """Send screening interview invite email to candidate. Returns True on success."""
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print(f"[EMAIL MOCK] Would send invite to {candidate_email} — link: {INTERVIEW_MODULE_URL}/interview/{session_id}?token={invite_token}")
        return True

    interview_link = f"{INTERVIEW_MODULE_URL}/interview/{session_id}?token={invite_token}"

    subject = f"Interview Invitation — {job_title} at {company_name}"

    html = f"""
    <div style="font-family: Inter, system-ui, sans-serif; max-width: 600px; margin: 0 auto; padding: 32px 24px; color: #1e293b;">
      <div style="margin-bottom: 32px;">
        <h2 style="font-size: 20px; font-weight: 700; color: #1e293b; margin: 0 0 4px;">
          Interview Invitation
        </h2>
        <p style="color: #64748b; font-size: 14px; margin: 0;">{company_name}</p>
      </div>

      <p style="font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
        Hi {candidate_name},
      </p>
      <p style="font-size: 15px; line-height: 1.6; margin-bottom: 16px;">
        Congratulations — your application for <strong>{job_title}</strong> has been shortlisted.
        We'd like to invite you to complete an AI-powered screening interview at your convenience.
      </p>
      <p style="font-size: 15px; line-height: 1.6; margin-bottom: 24px;">
        The interview is conducted entirely online and typically takes 30–45 minutes.
        You'll be asked technical and behavioural questions related to the role.
      </p>

      <div style="text-align: center; margin: 32px 0;">
        <a href="{interview_link}"
           style="display: inline-block; background-color: #4f46e5; color: white; font-weight: 600;
                  font-size: 15px; padding: 14px 32px; border-radius: 12px; text-decoration: none;">
          Start Interview →
        </a>
      </div>

      <p style="font-size: 13px; color: #94a3b8; text-align: center; margin-top: 8px;">
        This link expires in {expires_hours} hours and can only be used once.
      </p>

      <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 32px 0;" />
      <p style="font-size: 13px; color: #94a3b8;">
        If you have any questions, reply to this email.<br />
        Good luck, {candidate_name.split()[0]}!
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{company_name} Recruiting <{GMAIL_USER}>"
    msg["To"] = candidate_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, candidate_email, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] Failed to send to {candidate_email}: {e}")
        return False
