import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASS     = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM     = os.getenv("SMTP_FROM", "MedClinic No-Reply <no-reply@mediclinic.com>")
SMTP_REPLY_TO = os.getenv("SMTP_REPLY_TO", "noreply@mediclinic.com")
CLINIC_NAME   = os.getenv("CLINIC_NAME", "MedClinic")


def _send(to: str, subject: str, html: str) -> bool:
    if not SMTP_USER or not SMTP_PASS or SMTP_PASS == "your_gmail_app_password_here":
        print(f"[Email] SMTP not configured — skipping email to {to}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"]  = subject
        msg["From"]     = SMTP_FROM
        msg["To"]       = to
        msg["Reply-To"] = SMTP_REPLY_TO
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.login(SMTP_USER, SMTP_PASS)
            srv.sendmail(SMTP_USER, to, msg.as_string())
        print(f"[Email] Sent '{subject}' → {to}")
        return True
    except Exception as exc:
        print(f"[Email] Failed to send to {to}: {exc}")
        return False


def send_welcome_email(to: str, name: str, temp_pw: str, role: str) -> bool:
    subject = f"Welcome to {CLINIC_NAME} — Your Login Credentials"
    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:0;">
  <div style="background:#0d9488;padding:24px 32px;">
    <h1 style="color:#fff;margin:0;font-size:24px;">&#x2665; {CLINIC_NAME}</h1>
    <p style="color:#ccfbf1;margin:4px 0 0 0;font-size:14px;">Healthcare Management System</p>
  </div>
  <div style="padding:32px;background:#f9fafb;border:1px solid #e5e7eb;border-top:none;">
    <h2 style="color:#1f2937;margin-top:0;">Welcome, {name}!</h2>
    <p style="color:#4b5563;line-height:1.6;">
      Your account has been created on the <strong>{CLINIC_NAME}</strong> portal.
      Use the credentials below to sign in.
    </p>
    <div style="background:#fff;border:1px solid #d1fae5;border-radius:8px;padding:20px;margin:20px 0;">
      <table style="width:100%;border-collapse:collapse;">
        <tr>
          <td style="padding:6px 0;color:#6b7280;width:130px;font-size:14px;">Role</td>
          <td style="padding:6px 0;font-weight:600;color:#1f2937;">{role}</td>
        </tr>
        <tr>
          <td style="padding:6px 0;color:#6b7280;font-size:14px;">Email</td>
          <td style="padding:6px 0;font-weight:600;color:#1f2937;">{to}</td>
        </tr>
      </table>
      <div style="margin-top:16px;background:#f0fdf4;border-radius:6px;padding:14px 18px;">
        <p style="margin:0 0 6px;color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Temporary Password</p>
        <p style="margin:0;font-size:24px;font-weight:700;letter-spacing:3px;color:#0d9488;font-family:monospace;">{temp_pw}</p>
      </div>
    </div>
    <p style="color:#dc2626;font-weight:600;font-size:14px;">
      &#9888;&nbsp; You will be required to set a new password on your first login.
    </p>
    <p style="color:#6b7280;font-size:13px;">
      If you did not expect this email, please contact your system administrator.
    </p>
  </div>
  <div style="padding:16px;text-align:center;color:#9ca3af;font-size:12px;">
    &copy; {CLINIC_NAME} Healthcare Management System
  </div>
</body></html>"""
    return _send(to, subject, html)


def send_reactivation_email(to: str, name: str, temp_pw: str) -> bool:
    subject = f"{CLINIC_NAME} — Account Reactivated"
    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:0;">
  <div style="background:#0d9488;padding:24px 32px;">
    <h1 style="color:#fff;margin:0;font-size:24px;">&#x2665; {CLINIC_NAME}</h1>
    <p style="color:#ccfbf1;margin:4px 0 0 0;font-size:14px;">Healthcare Management System</p>
  </div>
  <div style="padding:32px;background:#f9fafb;border:1px solid #e5e7eb;border-top:none;">
    <h2 style="color:#1f2937;margin-top:0;">Welcome back, {name}!</h2>
    <p style="color:#4b5563;line-height:1.6;">
      Your account on the <strong>{CLINIC_NAME}</strong> portal has been reactivated by an administrator.
      For your security, a new temporary password has been generated. Use it to sign in below.
    </p>
    <div style="background:#fff;border:1px solid #d1fae5;border-radius:8px;padding:20px;margin:20px 0;">
      <div style="background:#f0fdf4;border-radius:6px;padding:14px 18px;">
        <p style="margin:0 0 6px;color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:1px;">New Temporary Password</p>
        <p style="margin:0;font-size:24px;font-weight:700;letter-spacing:3px;color:#0d9488;font-family:monospace;">{temp_pw}</p>
      </div>
    </div>
    <p style="color:#dc2626;font-weight:600;font-size:14px;">
      &#9888;&nbsp; You will be required to set a new password on your next login.
    </p>
    <p style="color:#6b7280;font-size:13px;">
      If you believe this was a mistake, please contact your system administrator.
    </p>
  </div>
  <div style="padding:16px;text-align:center;color:#9ca3af;font-size:12px;">
    &copy; {CLINIC_NAME} Healthcare Management System
  </div>
</body></html>"""
    return _send(to, subject, html)


def send_reset_email(to: str, name: str, temp_pw: str) -> bool:
    subject = f"{CLINIC_NAME} — Password Reset"
    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:0;">
  <div style="background:#0d9488;padding:24px 32px;">
    <h1 style="color:#fff;margin:0;font-size:24px;">&#x2665; {CLINIC_NAME}</h1>
    <p style="color:#ccfbf1;margin:4px 0 0 0;font-size:14px;">Healthcare Management System</p>
  </div>
  <div style="padding:32px;background:#f9fafb;border:1px solid #e5e7eb;border-top:none;">
    <h2 style="color:#1f2937;margin-top:0;">Password Reset — {name}</h2>
    <p style="color:#4b5563;line-height:1.6;">
      Your password has been reset by an administrator.
      Use the temporary password below to sign in.
    </p>
    <div style="background:#fff;border:1px solid #fde68a;border-radius:8px;padding:20px;margin:20px 0;">
      <div style="background:#fffbf0;border-radius:6px;padding:14px 18px;">
        <p style="margin:0 0 6px;color:#6b7280;font-size:12px;text-transform:uppercase;letter-spacing:1px;">New Temporary Password</p>
        <p style="margin:0;font-size:24px;font-weight:700;letter-spacing:3px;color:#d97706;font-family:monospace;">{temp_pw}</p>
      </div>
    </div>
    <p style="color:#dc2626;font-weight:600;font-size:14px;">
      &#9888;&nbsp; You will be required to set a new password on your first login.
    </p>
    <p style="color:#6b7280;font-size:13px;">
      If you did not request a password reset, contact your administrator immediately.
    </p>
  </div>
  <div style="padding:16px;text-align:center;color:#9ca3af;font-size:12px;">
    &copy; {CLINIC_NAME} Healthcare Management System
  </div>
</body></html>"""
    return _send(to, subject, html)
