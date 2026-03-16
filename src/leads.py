"""
leads.py
Handles multi-turn lead capture flow and writes to Google Sheets.
"""
from __future__ import annotations

import os
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Lead data model ──────────────────────────────────────────────────────────
@dataclass
class Lead:
    chat_id: str
    name: Optional[str]     = None
    email: Optional[str]    = None
    enquiry: Optional[str]  = None
    platform: str           = "telegram"
    timestamp: str          = field(default_factory=lambda: datetime.utcnow().isoformat())

# ── Lead capture state machine ───────────────────────────────────────────────
# States:  idle → ask_name → ask_email → ask_enquiry → done
LEAD_SESSIONS: dict[str, dict] = {}   # chat_id → {step, lead}

ENQUIRY_TYPES = ["EV Charger Installation", "Solar Panel Installation", "Pricing / Quote", "Maintenance / Fault", "Other"]

def start_lead_flow(chat_id: str) -> str:
    """Initialise lead capture for a given chat."""
    LEAD_SESSIONS[chat_id] = {"step": "ask_name", "lead": Lead(chat_id=chat_id)}
    return (
        "Great! I'd love to connect you with our team. 😊\n\n"
        "Let me grab a few quick details.\n\n"
        "*What's your name?*"
    )

def is_in_lead_flow(chat_id: str) -> bool:
    return chat_id in LEAD_SESSIONS and LEAD_SESSIONS[chat_id]["step"] != "done"

def handle_lead_step(chat_id: str, text: str) -> tuple[str, bool]:
    """
    Process one step of the lead capture flow.
    Returns (reply_text, is_complete).
    """
    session = LEAD_SESSIONS.get(chat_id)
    if not session:
        return ("Something went wrong. Please try again.", False)

    step = session["step"]
    lead: Lead = session["lead"]

    if step == "ask_name":
        lead.name = text.strip()
        session["step"] = "ask_email"
        return (f"Nice to meet you, {lead.name}! 👋\n\n*What's your email address?*", False)

    elif step == "ask_email":
        # basic validation
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", text.strip()):
            return ("Hmm, that doesn't look like a valid email. Could you try again?", False)
        lead.email = text.strip()
        session["step"] = "ask_enquiry"
        options = "\n".join([f"{i+1}. {e}" for i, e in enumerate(ENQUIRY_TYPES)])
        return (
            f"Perfect! And what are you enquiring about?\n\n{options}\n\n"
            "_(Reply with a number or type your enquiry)_",
            False,
        )

    elif step == "ask_enquiry":
        # accept number or free text
        t = text.strip()
        if t.isdigit() and 1 <= int(t) <= len(ENQUIRY_TYPES):
            lead.enquiry = ENQUIRY_TYPES[int(t) - 1]
        else:
            lead.enquiry = t
        session["step"] = "done"

        # Write to Google Sheets
        _save_lead(lead)

        reply = (
            f"✅ *Thank you, {lead.name}!*\n\n"
            f"We've noted your enquiry about *{lead.enquiry}*. "
            f"Our team will reach out to you at {lead.email} shortly.\n\n"
            "Is there anything else I can help you with in the meantime?"
        )
        return (reply, True)

    return ("Let me restart the form for you. What's your name?", False)


def _save_lead(lead: Lead) -> None:
    """Write the completed lead to Google Sheets."""
    sheet_id = os.getenv("GOOGLE_SHEET_ID")
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/google_service_account.json")

    if not sheet_id or not os.path.exists(creds_path):
        logger.warning("Google Sheets not configured — lead not saved to sheet.")
        logger.info(f"Lead captured (local): {lead}")
        return

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        ws = sh.sheet1

        # Add header row if sheet is empty
        if ws.row_count == 0 or ws.cell(1, 1).value is None:
            ws.append_row(["Timestamp", "Name", "Email", "Enquiry", "Platform", "Chat ID"])

        ws.append_row([
            lead.timestamp,
            lead.name,
            lead.email,
            lead.enquiry,
            lead.platform,
            lead.chat_id,
        ])
        logger.info(f"Lead saved to Google Sheets: {lead.email}")
    except Exception as e:
        logger.error(f"Failed to save lead to Google Sheets: {e}")
