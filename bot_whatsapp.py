"""
bot_whatsapp.py
WhatsApp webhook handler via Twilio — FastAPI app.
Run: uvicorn bot_whatsapp:app --port 8000
Expose with: ngrok http 8000
Set ngrok URL as: https://xxx.ngrok.io/whatsapp in Twilio sandbox webhook config.
"""
from __future__ import annotations

import logging
import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Form, Response
from twilio.twiml.messaging_response import MessagingResponse

from src.rag_pipeline import build_kb, retrieve_context
from src.llm_client import chat
from src.intent import detect_intent
from src.leads import start_lead_flow, is_in_lead_flow, handle_lead_step, LEAD_SESSIONS
from src.escalation import trigger_escalation
from src import session as sess_mgr

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)

app = FastAPI(title="SuperCharge SG WhatsApp Bot")

GREETING = (
    "👋 Welcome to SuperCharge SG!\n\n"
    "I'm SuperBot, your AI assistant for EV charging and solar energy. I can help with:\n"
    "⚡ EV Charger installation & pricing\n"
    "☀️ Solar panel installation\n"
    "📋 TR25 compliance & ECIS credits\n"
    "🔧 Fault reports & maintenance\n"
    "📞 Connecting you with our team\n\n"
    "What can I help you with today?"
)

@app.on_event("startup")
async def startup():
    logger.info("Building / loading knowledge base …")
    build_kb()
    logger.info("Knowledge base ready.")

@app.post("/whatsapp")
async def whatsapp_webhook(Body: str = Form(), From: str = Form()):
    """Twilio posts incoming WhatsApp messages here."""
    chat_id  = From   # e.g. whatsapp:+6591234567
    user_msg = Body.strip()
    logger.info(f"[WA] [{chat_id}]: {user_msg[:80]}")

    reply = await _process_message(chat_id, user_msg, platform="whatsapp")

    twiml = MessagingResponse()
    twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")

async def _process_message(chat_id: str, user_msg: str, platform: str = "whatsapp") -> str:
    """Shared message processing logic (same as Telegram bot)."""

    # Lead flow
    if is_in_lead_flow(chat_id):
        # Mark platform
        if chat_id in LEAD_SESSIONS:
            LEAD_SESSIONS[chat_id]["lead"].platform = platform
        reply, done = handle_lead_step(chat_id, user_msg)
        if done:
            sess_mgr.reset_failed_intents(chat_id)
        return reply  # strip markdown for WhatsApp

    intent = detect_intent(user_msg)

    if intent == "greeting":
        sess_mgr.reset_failed_intents(chat_id)
        return GREETING

    if intent == "escalation":
        history = sess_mgr.get_history(chat_id)
        return trigger_escalation(chat_id, chat_id, history, reason="User requested human agent")

    if intent == "lead":
        sess_mgr.add_message(chat_id, "user", user_msg)
        return start_lead_flow(chat_id)

    # RAG + LLM
    sess_mgr.add_message(chat_id, "user", user_msg)
    history = sess_mgr.get_history(chat_id)
    context_text = retrieve_context(user_msg)

    if not context_text.strip():
        failed = sess_mgr.increment_failed_intents(chat_id)
        if failed >= 3:
            esc = trigger_escalation(chat_id, chat_id, history, reason="3 consecutive failed intents")
            sess_mgr.reset_failed_intents(chat_id)
            return esc
        return (
            "Hmm, I couldn't find specific information about that. "
            "Could you rephrase, or would you like me to connect you with our team?"
        )

    sess_mgr.reset_failed_intents(chat_id)
    reply = chat(history, context_text)
    sess_mgr.add_message(chat_id, "assistant", reply)

    # Strip markdown bold/italic for WhatsApp plain text
    import re
    reply = re.sub(r"\*\*?(.*?)\*\*?", r"\1", reply)
    reply = re.sub(r"_(.*?)_", r"\1", reply)
    return reply

@app.get("/health")
async def health():
    return {"status": "ok", "service": "supercharge-whatsapp-bot"}
