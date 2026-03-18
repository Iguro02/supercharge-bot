"""
leads.py
Handles multi-turn lead capture flow and writes to Google Sheets.
Headers are always enforced on row 1. Columns are always consistent.
Supports local file credentials and base64-encoded credentials for Railway.
"""
from __future__ import annotations

import os
import json
import base64
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

HEADERS = ["Timestamp", "Name", "Email", "Enquiry Type", "Platform", "Chat ID"]

@dataclass
class Lead:
    chat_id:   str
    name:      Optional[str] = None
    email:     Optional[str] = None
    enquiry:   Optional[str] = None
    platform:  str           = "telegram"
    timestamp: str           = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))

LEAD_SESSIONS: dict[str, dict] = {}
ENQUIRY_TYPES = [
    "EV Charger Installation",
    "Solar Panel Installation",
    "Pricing / Quote",
    "Maintenance / Fault",
    "Other",
]

def start_lead_flow(chat_id: str) -> str:
    LEAD_SESSIONS[chat_id] = {"step": "ask_name", "lead": Lead(chat_id=chat_id)}
    return (
        "Great! I'd love to connect you with our team.\n\n"
        "Let me grab a few quick details.\n\n"
        "What's your name?"
    )

def is_in_lead_flow(chat_id: str) -> bool:
    return chat_id in LEAD_SESSIONS and LEAD_SESSIONS[chat_id]["step"] != "done"

def handle_lead_step(chat_id: str, text: str) -> tuple[str, bool]:
    session = LEAD_SESSIONS.get(chat_id)
    if not session:
        return ("Something went wrong. Please try again.", False)

    step = session["step"]
    lead: Lead = session["lead"]

    if step == "ask_name":
        lead.name = text.strip()
        session["step"] = "ask_email"
        return (f"Nice to meet you, {lead.name}! What's your email address?", False)

    elif step == "ask_email":
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", text.strip()):
            return ("Hmm, that doesn't look like a valid email. Could you try again?", False)
        lead.email = text.strip()
        session["step"] = "ask_enquiry"
        options = "\n".join([f"{i+1}. {e}" for i, e in enumerate(ENQUIRY_TYPES)])
        return (
            f"Perfect! What are you enquiring about?\n\n{options}\n\nReply with a number or describe your enquiry.",
            False,
        )

    elif step == "ask_enquiry":
        t = text.strip()
        if t.isdigit() and 1 <= int(t) <= len(ENQUIRY_TYPES):
            lead.enquiry = ENQUIRY_TYPES[int(t) - 1]
        else:
            lead.enquiry = t
        session["step"] = "done"
        _save_lead(lead)
        return (
            f"Thank you, {lead.name}!\n\n"
            f"We've noted your enquiry about {lead.enquiry}. "
            f"Our team will reach out to you at {lead.email} shortly.\n\n"
            "Is there anything else I can help you with?",
            True,
        )

    return ("Let me restart the form. What's your name?", False)


def _get_worksheet():
    """Authenticate and return the Google Sheet worksheet."""
    sheet_id  = os.getenv("GOOGLE_SHEET_ID")
    creds_b64 = os.getenv("GOOGLE_CREDENTIALS_B64")
    creds_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "credentials/google_service_account.json")

    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID not set")

    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    if creds_b64:
        creds_json = json.loads(base64.b64decode(creds_b64).decode())
        creds = Credentials.from_service_account_info(creds_json, scopes=scopes)
    elif os.path.exists(creds_path):
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    else:
        raise FileNotFoundError("No Google credentials found")

    gc = gspread.authorize(creds)
    return gc.open_by_key(sheet_id).sheet1


def _ensure_headers(ws) -> None:
    """Always enforce correct headers on row 1."""
    try:
        existing = ws.row_values(1)
    except Exception:
        existing = []

    if existing != HEADERS:
        ws.update("A1", [HEADERS])
        logger.info("Header row written/corrected in Google Sheet.")


def _save_lead(lead: Lead) -> None:
    """Write lead to Google Sheets with enforced headers and consistent columns."""
    try:
        ws = _get_worksheet()
        _ensure_headers(ws)

        # Data row — must match HEADERS order exactly
        row = [
            lead.timestamp,  # Timestamp
            lead.name,       # Name
            lead.email,      # Email
            lead.enquiry,    # Enquiry Type
            lead.platform,   # Platform
            lead.chat_id,    # Chat ID
        ]

        ws.append_row(row, value_input_option="USER_ENTERED")
        logger.info(f"Lead saved to Google Sheets: {lead.email}")

    except ValueError as e:
        logger.warning(f"Google Sheets config missing: {e} — lead logged locally.")
        logger.info(f"Lead: name={lead.name}, email={lead.email}, enquiry={lead.enquiry}")
    except Exception as e:
        logger.error(f"Failed to save lead to Google Sheets: {e}")
        logger.info(f"Lead: name={lead.name}, email={lead.email}, enquiry={lead.enquiry}")
