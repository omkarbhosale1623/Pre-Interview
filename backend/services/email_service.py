"""
services/email_service.py — SMTP email sending for Pre-Interview AI.
Handles: candidate invite emails + recruiter report emails.
"""
from __future__ import annotations
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, TYPE_CHECKING

from config import settings

if TYPE_CHECKING:
    from models.schemas import EvaluationReport

logger = logging.getLogger(__name__)

BRAND = "Pre-Interview AI"
BRAND_COLOR = "#c9a84c"
BG_DARK = "#03060f"
SURFACE = "#080f1e"


def _smtp_send(to_email: str, subject: str, html: str, plain: str, from_name: str) -> bool:
    if not settings.smtp_username or not settings.smtp_password:
        logger.warning("SMTP not configured. Email not sent. To: %s | Subject: %s", to_email, subject)
        return False
    from_addr = settings.email_from or settings.smtp_username
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = to_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    try:
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as smtp:
            smtp.ehlo(); smtp.starttls()
            smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.sendmail(from_addr, to_email, msg.as_string())
        logger.info("Email sent → %s | %s", to_email, subject)
        return True
    except Exception as e:
        logger.warning("Email failed → %s: %s", to_email, e)
        return False


def send_invite_email(
    to_email: str, candidate_name: str, candidate_role: Optional[str],
    company_name: Optional[str], interviewer_name: Optional[str],
    scheduled_at_str: str, interview_link: str, bank_name: str,
    question_count: int, notes: Optional[str] = None,
    is_immediate: bool = False, link_expires_at: Optional[datetime] = None,
) -> bool:
    company = company_name or "Your Recruiter"
    role_display = candidate_role or "the open position"
    expiry_note = ""
    if not is_immediate and link_expires_at:
        expiry_note = f"<p style='color:#e8a020;font-size:13px;margin:0;'><strong>⏰ Link expires:</strong> {link_expires_at.strftime('%B %d, %Y at %I:%M %p UTC')} (30 minutes after scheduled start)</p>"

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Interview Invitation – {company}</title></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:40px 20px;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.12);">
<tr><td style="background:{BG_DARK};padding:36px 44px;text-align:center;">
  <div style="font-size:13px;color:{BRAND_COLOR};letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">AI-POWERED SCREENING</div>
  <h1 style="margin:0;font-size:30px;font-weight:800;color:#fff;letter-spacing:-0.5px;">🎙 {BRAND}</h1>
</td></tr>
<tr><td style="padding:40px 44px;">
  <p style="font-size:17px;color:#111;margin:0 0 8px;">Hello <strong>{candidate_name}</strong>,</p>
  <p style="font-size:15px;color:#444;line-height:1.7;margin:0 0 28px;">
    You've been selected to complete an AI-powered screening interview for the
    <strong>{role_display}</strong> position at <strong>{company}</strong>.
  </p>
  <div style="background:#f7f8fa;border:1px solid #e8eaed;border-radius:14px;padding:26px 30px;margin-bottom:24px;">
    <h2 style="margin:0 0 18px;font-size:13px;font-weight:700;color:{BRAND_COLOR};letter-spacing:2px;text-transform:uppercase;">Interview Details</h2>
    {"<p style='margin:0 0 10px;'><strong>Role:</strong> " + candidate_role + "</p>" if candidate_role else ""}
    <p style="margin:0 0 10px;"><strong>Scheduled:</strong> {scheduled_at_str}</p>
    <p style="margin:0 0 10px;"><strong>Format:</strong> AI voice interview — {question_count} questions</p>
    <p style="margin:0;"><strong>Coordinator:</strong> {interviewer_name or company}</p>
  </div>
  {f'<div style="background:#fffbf0;border:1px solid #fde8b0;border-radius:10px;padding:16px 20px;margin-bottom:24px;"><p style="margin:0;font-size:14px;color:#7a5500;"><strong>📝 Notes:</strong> {notes}</p></div>' if notes else ''}
  {f'<div style="background:#fff9ec;border:1px solid #f0d080;border-radius:10px;padding:14px 20px;margin-bottom:24px;">{expiry_note}</div>' if expiry_note else ''}
  <div style="text-align:center;margin:32px 0;">
    <a href="{interview_link}" style="display:inline-block;background:{BRAND_COLOR};color:#000;font-weight:800;font-size:16px;padding:18px 44px;border-radius:12px;text-decoration:none;letter-spacing:0.5px;">▶ Begin Interview</a>
    <p style="margin:14px 0 0;font-size:12px;color:#999;">Or paste this link in your browser:<br><span style="color:#3a7fe8;">{interview_link}</span></p>
  </div>
  <div style="background:#f0f4ff;border-radius:12px;padding:18px 22px;">
    <p style="margin:0;font-size:13px;color:#4a5a8a;line-height:1.6;">
      <strong>💡 Before you start:</strong> Use Chrome or Edge browser · Find a quiet space ·
      Allow microphone access · Speak clearly — the AI listens and responds automatically.
    </p>
  </div>
</td></tr>
<tr><td style="background:#f7f8fa;padding:20px 44px;border-top:1px solid #e8eaed;text-align:center;">
  <p style="margin:0;font-size:12px;color:#999;">This link is unique to you — do not share it.<br>
  Sent by <strong>{company}</strong> via {BRAND}.</p>
</td></tr>
</table></td></tr></table></body></html>"""

    plain = f"""Hello {candidate_name},

You've been invited to complete an AI interview for {role_display} at {company}.

DETAILS
Scheduled: {scheduled_at_str}
Format: AI voice interview ({question_count} questions)
Coordinator: {interviewer_name or company}
{"Notes: " + notes if notes else ""}
{"Link expires: " + link_expires_at.strftime('%B %d at %I:%M %p UTC') if link_expires_at else ""}

Start your interview:
{interview_link}

Tips: Use Chrome/Edge, quiet space, allow microphone access.

— {BRAND}"""

    subject = f"Interview Invitation: {role_display} at {company}"
    return _smtp_send(to_email, subject, html, plain, f"{company} via {BRAND}")


def send_report_to_recruiter(report: "EvaluationReport", recruiter_email: str, candidate_email: Optional[str] = None) -> bool:
    """Send the full evaluation report to the recruiter after interview completion."""
    score_color = "#00c896" if report.overall_score >= 75 else ("#e8a020" if report.overall_score >= 55 else "#ff4560")
    rec_configs = {
        "Strong Hire": ("🌟", "#00c896"), "Hire": ("✅", "#00c896"),
        "Consider": ("🤔", "#e8a020"), "No Hire": ("❌", "#ff4560"),
    }
    rec_icon, rec_color = rec_configs.get(report.recommendation, ("🤔", "#e8a020"))
    role = report.candidate_role or "the position"

    q_rows = ""
    for i, qe in enumerate(report.question_evaluations, 1):
        sc = "#00c896" if qe.score >= 75 else ("#e8a020" if qe.score >= 55 else "#ff4560")
        skipped_badge = '<span style="background:#ff4560;color:#fff;font-size:10px;padding:2px 7px;border-radius:10px;margin-left:6px;">SKIPPED</span>' if qe.was_skipped else ""
        q_rows += f"""
        <div style="border:1px solid #e8eaed;border-radius:12px;padding:20px;margin-bottom:16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;">
            <div style="flex:1;"><span style="font-size:11px;color:{BRAND_COLOR};font-weight:700;text-transform:uppercase;letter-spacing:1px;">Q{i}{' · ' + qe.topic if qe.topic else ''}</span>{skipped_badge}
            <p style="font-size:15px;color:#111;margin:6px 0 0;font-weight:600;">{qe.question_text}</p></div>
            <div style="text-align:center;margin-left:16px;"><span style="font-size:28px;font-weight:800;color:{sc};">{qe.score}</span><br><span style="font-size:10px;color:{sc};text-transform:uppercase;">{qe.rating.upper()}</span></div>
          </div>
          <div style="background:#f7f8fa;border-radius:8px;padding:12px;margin-bottom:12px;">
            <p style="font-size:11px;color:#999;margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Candidate's Answer</p>
            <p style="font-size:13px;color:#555;margin:0;line-height:1.6;">{qe.answer_transcript or "(No response)"}</p>
          </div>
          <p style="font-size:14px;color:#333;line-height:1.6;margin:0 0 8px;">{qe.detailed_feedback or qe.feedback}</p>
          {"<p style='font-size:12px;color:#4a5a8a;'>Keywords: " + ", ".join(f"<strong>{k}</strong>" for k in qe.keywords_hit) + "</p>" if qe.keywords_hit else ""}
        </div>"""

    risk_section = ""
    if report.risk_flags:
        flags = "".join(f"<li style='margin-bottom:6px;color:#cc2233;'>{f}</li>" for f in report.risk_flags)
        risk_section = f"""<div style="background:#fff0f2;border:1px solid #ffc0c8;border-radius:12px;padding:20px;margin-bottom:20px;">
        <h3 style="margin:0 0 12px;font-size:13px;color:#cc2233;font-weight:700;text-transform:uppercase;letter-spacing:1px;">⚠ Risk Flags</h3>
        <ul style="margin:0;padding-left:20px;">{flags}</ul></div>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:40px 20px;">
<tr><td align="center">
<table width="720" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.12);">
<tr><td style="background:{BG_DARK};padding:32px 44px;">
  <div style="font-size:11px;color:{BRAND_COLOR};letter-spacing:3px;text-transform:uppercase;margin-bottom:8px;">EVALUATION REPORT</div>
  <h1 style="margin:0;font-size:26px;font-weight:800;color:#fff;">🎙 {BRAND}</h1>
</td></tr>
<tr><td style="padding:36px 44px;">
  <!-- Hero -->
  <div style="display:flex;justify-content:space-between;align-items:center;background:#f7f8fa;border-radius:14px;padding:24px 28px;margin-bottom:24px;">
    <div>
      <h2 style="margin:0;font-size:24px;font-weight:800;color:#111;">{report.candidate_name}</h2>
      <p style="margin:4px 0 0;font-size:14px;color:#666;">{role}</p>
      <p style="margin:6px 0 0;font-size:12px;color:#999;font-family:monospace;">{report.generated_at.strftime('%Y-%m-%d %H:%M UTC')} · {len(report.question_evaluations)} questions</p>
    </div>
    <div style="text-align:center;">
      <div style="font-size:48px;font-weight:800;color:{score_color};line-height:1;">{report.overall_score}</div>
      <div style="font-size:11px;color:{score_color};letter-spacing:2px;text-transform:uppercase;">/ 100</div>
    </div>
  </div>
  <!-- Recommendation -->
  <div style="background:{rec_color}18;border:2px solid {rec_color}40;border-radius:14px;padding:20px 28px;margin-bottom:24px;display:flex;align-items:center;gap:16px;">
    <span style="font-size:36px;">{rec_icon}</span>
    <div>
      <div style="font-size:22px;font-weight:800;color:{rec_color};">{report.recommendation}</div>
      <div style="font-size:13px;color:#666;">Overall: <strong style="color:{rec_color};">{report.overall_rating.upper()}</strong></div>
    </div>
  </div>
  <!-- Executive Summary -->
  <div style="margin-bottom:24px;">
    <h3 style="font-size:13px;font-weight:700;color:{BRAND_COLOR};text-transform:uppercase;letter-spacing:1px;margin:0 0 12px;">Executive Summary</h3>
    <p style="font-size:14px;color:#333;line-height:1.8;margin:0;">{report.executive_summary or report.summary}</p>
  </div>
  <!-- Hiring Notes (private) -->
  {"<div style='background:#fff9ec;border:1px solid #f0d080;border-radius:12px;padding:18px 22px;margin-bottom:20px;'><h3 style='font-size:12px;font-weight:700;color:#7a5500;margin:0 0 8px;text-transform:uppercase;letter-spacing:1px;'>🔒 Private Hiring Notes</h3><p style='font-size:14px;color:#333;margin:0;line-height:1.7;'>" + report.hiring_notes + "</p></div>" if report.hiring_notes else ""}
  <!-- Risk flags -->
  {risk_section}
  <!-- Strengths & Improvements -->
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px;">
    <div style="background:#f0fdf8;border:1px solid #c0f0e0;border-radius:12px;padding:18px;">
      <h3 style="font-size:12px;font-weight:700;color:#00a878;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">✓ Key Strengths</h3>
      {"".join(f"<p style='font-size:13px;color:#333;margin:0 0 8px;'>• {s}</p>" for s in report.strengths)}
    </div>
    <div style="background:#fff9ec;border:1px solid #f0d080;border-radius:12px;padding:18px;">
      <h3 style="font-size:12px;font-weight:700;color:#c08000;margin:0 0 12px;text-transform:uppercase;letter-spacing:1px;">↑ Areas to Improve</h3>
      {"".join(f"<p style='font-size:13px;color:#333;margin:0 0 8px;'>• {s}</p>" for s in report.improvements)}
    </div>
  </div>
  <!-- Q&A Breakdown -->
  <h3 style="font-size:13px;font-weight:700;color:{BRAND_COLOR};text-transform:uppercase;letter-spacing:1px;margin:0 0 16px;">Question-by-Question Breakdown</h3>
  {q_rows}
</td></tr>
<tr><td style="background:#f7f8fa;padding:20px 44px;border-top:1px solid #e8eaed;text-align:center;">
  <p style="margin:0;font-size:12px;color:#999;">Evaluation generated by {BRAND} · Confidential recruiter report</p>
</td></tr>
</table></td></tr></table></body></html>"""

    plain = f"""PRE-INTERVIEW AI — EVALUATION REPORT
{'='*60}
Candidate: {report.candidate_name}
Role: {role}
Score: {report.overall_score}/100 ({report.overall_rating.upper()})
Recommendation: {report.recommendation}
Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}

EXECUTIVE SUMMARY
{report.executive_summary or report.summary}

HIRING NOTES (Private)
{report.hiring_notes}

{'RISK FLAGS: ' + ' | '.join(report.risk_flags) if report.risk_flags else ''}

STRENGTHS
{chr(10).join('• ' + s for s in report.strengths)}

IMPROVEMENTS
{chr(10).join('• ' + s for s in report.improvements)}

{'='*60}
Q&A BREAKDOWN
{'='*60}
{chr(10).join(f'Q{i+1}: {qe.question_text}{chr(10)}Score: {qe.score}/100 ({qe.rating.upper()}){chr(10)}Answer: {qe.answer_transcript}{chr(10)}Feedback: {qe.detailed_feedback or qe.feedback}{chr(10)}' for i, qe in enumerate(report.question_evaluations))}

— {BRAND}"""

    subject = f"[Pre-Interview AI] Evaluation: {report.candidate_name} — {report.recommendation}"
    return _smtp_send(recruiter_email, subject, html, plain, BRAND)


def send_thankyou_to_candidate(candidate_email: str, candidate_name: str, company_name: Optional[str] = None) -> bool:
    company = company_name or "the hiring team"
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:40px 20px;">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.12);">
<tr><td style="background:{BG_DARK};padding:36px 40px;text-align:center;">
  <h1 style="margin:0;font-size:26px;font-weight:800;color:#fff;">🎙 {BRAND}</h1>
</td></tr>
<tr><td style="padding:40px;text-align:center;">
  <div style="font-size:60px;margin-bottom:20px;">🎉</div>
  <h2 style="font-size:26px;font-weight:800;color:#111;margin:0 0 12px;">Interview Complete!</h2>
  <p style="font-size:15px;color:#444;line-height:1.7;margin:0 0 24px;">
    Thank you, <strong>{candidate_name}</strong>. Your responses have been submitted and {company} will be in touch with next steps.
  </p>
  <div style="background:#f0f8ff;border-radius:12px;padding:18px 22px;text-align:left;">
    <p style="font-size:13px;color:#4a5a8a;margin:0;line-height:1.6;">✓ Your interview has been recorded and submitted<br>✓ Your responses are being evaluated<br>✓ You will hear back from the team shortly</p>
  </div>
</td></tr>
<tr><td style="background:#f7f8fa;padding:20px 40px;text-align:center;border-top:1px solid #e8eaed;">
  <p style="margin:0;font-size:12px;color:#999;">— {BRAND}</p>
</td></tr>
</table></td></tr></table></body></html>"""
    plain = f"""Hello {candidate_name},

Your interview is complete! Thank you for taking the time.

{company} will review your responses and be in touch with the next steps.

— {BRAND}"""
    subject = f"Interview Submitted — {BRAND}"
    return _smtp_send(candidate_email, subject, html, plain, BRAND)


def send_test_email(to_email: str) -> bool:
    """Simple helper used during setup to verify SMTP configuration."""
    subject = "[Pre-Interview AI] SMTP Test"
    html = "<p>This is a test email from Pre-Interview AI. If you received it, your SMTP settings are correct.</p>"
    plain = "This is a test email from Pre-Interview AI. If you received it, your SMTP settings are correct."
    return _smtp_send(to_email, subject, html, plain, BRAND)
