# project/email_utils.py
import os
import resend

# Load API key from environment variable (correct)
resend.api_key = os.environ.get("RESEND_API_KEY")

# Default from email (used if env var not set)
FROM_EMAIL = os.environ.get(
    "RESEND_FROM_EMAIL",
    "onboarding@resend.dev"
)



def send_exam_confirmation(to_email, subject, html_body):
    if not resend.api_key:
        print("⚠ RESEND_API_KEY not set; skipping email send.")
        return None

    params = {
        "from": FROM_EMAIL,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }

    try:
        email = resend.Emails.send(params)
        print("📧 Email sent:", email)
        return email

    except Exception as e:
        print("❌ Error sending email:", e)
        return None
