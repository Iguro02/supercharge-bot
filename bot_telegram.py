"""
bot_telegram.py
Main Telegram bot — python-telegram-bot v20 (async).
Run: python bot_telegram.py
"""
from __future__ import annotations

import re
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# local modules
from src.rag_pipeline import build_kb, retrieve_context
from src.llm_client import chat
from src.intent import detect_intent
from src.leads import start_lead_flow, is_in_lead_flow, handle_lead_step
from src.escalation import trigger_escalation
from src import session as sess_mgr

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=os.getenv("LOG_LEVEL", "INFO"),
)
logger = logging.getLogger(__name__)

# ── Helper: strip markdown that breaks Telegram ───────────────────────────────
def _safe(text: str) -> str:
    """Remove or escape markdown characters that cause Telegram parse errors."""
    # Remove bold/italic markers that are unmatched
    text = re.sub(r'\*{1,2}', '', text)
    text = re.sub(r'_{1,2}', '', text)
    text = re.sub(r'`{1,3}', '', text)
    return text.strip()

# ── Greeting message ──────────────────────────────────────────────────────────
GREETING = (
    "👋 Welcome to SuperCharge SG!\n\n"
    "I'm SuperBot, your AI assistant for all things EV charging and solar energy. "
    "I can help you with:\n\n"
    "⚡ EV Charger installation and pricing\n"
    "☀️ Solar panel installation\n"
    "📋 TR25 compliance and ECIS credits\n"
    "🔧 Fault reports and maintenance\n"
    "📞 Connecting you with our team\n\n"
    "What can I help you with today?"
)

# ── /start command ────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    sess_mgr.reset_failed_intents(chat_id)
    await update.message.reply_text(GREETING)

# ── /help command ─────────────────────────────────────────────────────────────
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "SuperBot — Quick Guide\n\n"
        "Just type your question naturally! Examples:\n\n"
        "• How much does a 5kWp solar system cost?\n"
        "• What is TR25?\n"
        "• Can I install EV charger in my condo?\n"
        "• I'm interested in solar panels\n"
        "• I need to speak to someone\n\n"
        "Commands:\n"
        "/start — Restart the bot\n"
        "/help — Show this message\n"
        "/reset — Clear conversation history"
    )
    await update.message.reply_text(help_text)

# ── /reset command ────────────────────────────────────────────────────────────
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    sess_mgr._sessions.pop(chat_id, None)
    await update.message.reply_text("Conversation reset! How can I help you today?")

# ── Main message handler ──────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_msg = update.message.text.strip()
    chat_id  = str(update.effective_chat.id)
    username = update.effective_user.username or update.effective_user.first_name or "User"

    logger.info(f"[{chat_id}] {username}: {user_msg[:80]}")

    # ── 1. Lead capture flow (takes priority) ─────────────────────────────
    if is_in_lead_flow(chat_id):
        reply, done = handle_lead_step(chat_id, user_msg)
        await update.message.reply_text(_safe(reply))
        if done:
            sess_mgr.reset_failed_intents(chat_id)
        return

    # ── 2. Intent detection ───────────────────────────────────────────────
    intent = detect_intent(user_msg)
    logger.info(f"[{chat_id}] Intent: {intent}")

    # ── 3. Route by intent ────────────────────────────────────────────────

    if intent == "greeting":
        await update.message.reply_text(GREETING)
        sess_mgr.reset_failed_intents(chat_id)
        return

    if intent == "escalation":
        history = sess_mgr.get_history(chat_id)
        reply = trigger_escalation(chat_id, username, history, reason="User requested human agent")
        await update.message.reply_text(_safe(reply))
        return

    if intent == "lead":
        sess_mgr.add_message(chat_id, "user", user_msg)
        reply = start_lead_flow(chat_id)
        await update.message.reply_text(_safe(reply))
        return

    # FAQ / price / fault / unknown → RAG + LLM
    sess_mgr.add_message(chat_id, "user", user_msg)
    history = sess_mgr.get_history(chat_id)
    context_text = retrieve_context(user_msg)

    if not context_text.strip():
        failed = sess_mgr.increment_failed_intents(chat_id)
        if failed >= 3:
            esc_reply = trigger_escalation(chat_id, username, history, reason="3 consecutive failed intents")
            await update.message.reply_text(_safe(esc_reply))
            sess_mgr.reset_failed_intents(chat_id)
            return
        await update.message.reply_text(
            "Hmm, I couldn't find specific information about that. 🤔\n\n"
            "Could you rephrase, or would you like me to connect you with our team?"
        )
        return

    sess_mgr.reset_failed_intents(chat_id)
    reply = chat(history, context_text)
    sess_mgr.add_message(chat_id, "assistant", reply)
    await update.message.reply_text(_safe(reply))


# ── Error handler ─────────────────────────────────────────────────────────────
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error: {context.error}")


# ── App entry point ───────────────────────────────────────────────────────────
def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in environment")

    logger.info("Building / loading knowledge base ...")
    build_kb()
    logger.info("Knowledge base ready.")

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help",  cmd_help))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("SuperBot is running ...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()