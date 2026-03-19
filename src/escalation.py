"""
escalation.py
Sends human handoff alerts via Slack + Brevo HTTP email API.
Brevo (formerly Sendinblue) allows sending to any email without domain verification.
No SMTP — works on Railway free tier.
"""
from __future__ import annotations

import os
import logging
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


def trigger_escalation(
    chat_id: str,
    username: str,
    history: list[dict],
    reason: str = "User requested human",
) -> str:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    summary_lines = []
    for msg in history[-6:]:
        role = "User" if msg["role"] == "user" else "Bot"
        summary_lines.append(f"{role}: {msg['content'][:200]}")
    summary_text = "\n".join(summary_lines) if summary_lines else "No prior messages"

    _send_slack(chat_id, username, timestamp, reason, summary_text)
    _send_email_brevo(chat_id, username, timestamp, reason, summary_text)

    return (
        "Of course! I'm flagging this conversation to our team right now.\n\n"
        "A SuperCharge SG team member will follow up with you shortly.\n\n"
        "In the meantime, you're also welcome to reach us directly:\n"
        "Email: yusuf@supercharge.sg\n"
        "Web: supercharge.sg\n\n"
        "Is there anything else I can help clarify while you wait?"
    )


# ── Slack ─────────────────────────────────────────────────────────────────────
def _send_slack(chat_id: str, username: str, timestamp: str, reason: str, summary: str) -> None:
    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook:
        logger.warning("SLACK_WEBHOOK_URL not set — Slack alert skipped.")
        return

    payload = {
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "SuperBot — Human Handoff Required"}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Chat ID:*\n`{chat_id}`"},
                    {"type": "mrkdwn", "text": f"*User:*\n{username or 'Unknown'}"},
                    {"type": "mrkdwn", "text": f"*Time (UTC):*\n{timestamp}"},
                    {"type": "mrkdwn", "text": f"*Reason:*\n{reason}"},
                ],
            },
            {"type": "divider"},
            {"type": "section", "text": {"type": "mrkdwn", "text": f"*Recent conversation:*\n```{summary}```"}},
        ]
    }

    try:
        resp = httpx.post(webhook, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info(f"Slack escalation alert sent for chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Slack webhook failed: {e}")


# ── Email via Brevo HTTP API (no domain verification needed) ──────────────────
def _send_email_brevo(chat_id: str, username: str, timestamp: str, reason: str, summary: str) -> None:
    api_key   = os.getenv("BREVO_API_KEY")
    to_addr   = os.getenv("ESCALATION_EMAIL_TO")
    from_addr = os.getenv("ESCALATION_EMAIL_FROM", "shameer1402@gmail.com")
    from_name = "SuperBot — SuperCharge SG"

    if not api_key:
        logger.error("EMAIL FAILED: BREVO_API_KEY not set in Railway environment variables.")
        return
    if not to_addr:
        logger.error("EMAIL FAILED: ESCALATION_EMAIL_TO not set in environment variables.")
        return

    logger.info(f"Sending email via Brevo HTTP API to {to_addr} ...")

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; color: #333;">
      <h2 style="color:#e85d04;">SuperBot — Human Handoff Required</h2>
      <table cellpadding="8" style="border-collapse:collapse; width:100%;">
        <tr><td style="font-weight:bold; width:120px;">Chat ID</td><td><code>{chat_id}</code></td></tr>
        <tr style="background:#f9f9f9;"><td style="font-weight:bold;">User</td><td>{username or 'Unknown'}</td></tr>
        <tr><td style="font-weight:bold;">Time (UTC)</td><td>{timestamp}</td></tr>
        <tr style="background:#f9f9f9;"><td style="font-weight:bold;">Reason</td><td>{reason}</td></tr>
      </table>
      <h3 style="margin-top:20px;">Recent Conversation</h3>
      <pre style="background:#f4f4f4; padding:12px; border-radius:6px; white-space:pre-wrap;">{summary}</pre>
      <p style="color:#888; font-size:12px; margin-top:20px;">Sent automatically by SuperBot · SuperCharge SG</p>
    </body></html>
    """

    payload = {
        "sender":  {"name": from_name, "email": from_addr},
        "to":      [{"email": to_addr}],
        "subject": f"[SuperBot] Human Handoff Required — Chat {chat_id}",
        "htmlContent": html_body,
    }

    try:
        resp = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": api_key,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info(f"Email sent successfully to {to_addr} via Brevo.")
        else:
            logger.error(f"Brevo API error {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.error(f"Brevo email failed: {e}")
