"""
llm_client.py
LLM wrapper — Google Gemini (primary) with graceful fallback message.
Set LLM_PROVIDER=gemini and GEMINI_API_KEY in your .env
"""
from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are SuperBot, the friendly and knowledgeable AI customer support assistant for SuperCharge SG — Singapore's leading EV charging and solar installation company.

Your personality:
- Warm, professional, and helpful
- You speak like a knowledgeable Singaporean team member — conversational but never sloppy
- You use local context naturally (e.g., HDB, MCST, SP Group, LTA, SGD)

Your rules:
1. ONLY answer from the provided knowledge base context. Never invent prices, specs, or facts.
2. If the context doesn't contain enough information, say: "That's a great question — for the most accurate answer, I'd recommend speaking with our team directly. Would you like me to help arrange that?"
3. Never give specific electrical engineering advice — always route those to our human team.
4. Keep answers concise but complete. Use bullet points for lists.
5. Always end with a helpful follow-up offer when relevant.
6. Prices are indicative — always advise the customer to contact SuperCharge for an exact quote.

Knowledge base context (answer only from this):
{context}
"""

def _build_gemini_contents(messages: list[dict], context: str) -> list[dict]:
    """Convert OpenAI-style message list to Gemini contents format."""
    system_text = SYSTEM_PROMPT.format(context=context)
    contents = []

    # Inject system prompt as the first user turn (Gemini 1.5 supports system_instruction separately)
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    return system_text, contents


def _gemini_chat(messages: list[dict], context: str) -> str:
    import google.generativeai as genai

    genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    system_text, contents = _build_gemini_contents(messages, context)

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",  
        system_instruction=system_text,
        generation_config={
            "max_output_tokens": 600,
            "temperature": 0.3,
        },
    )

    # Build chat history (all but last user message)
    history_for_chat = contents[:-1] if len(contents) > 1 else []
    last_user_msg = contents[-1]["parts"][0]["text"] if contents else ""

    chat_session = model.start_chat(history=history_for_chat)
    response = chat_session.send_message(last_user_msg)
    return response.text.strip()


def chat(messages: list[dict], context: str) -> str:
    """Send messages to Gemini and return the assistant reply."""
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    try:
        if provider == "gemini":
            return _gemini_chat(messages, context)
        else:
            # Fallback: try Gemini anyway
            return _gemini_chat(messages, context)
    except Exception as e:
        logger.error(f"LLM error ({provider}): {e}")
        return (
            "I'm having a little technical hiccup right now. 🙏 "
            "Please try again in a moment, or contact our team directly at supercharge.sg"
        )
