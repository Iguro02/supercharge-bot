"""
session.py
In-memory session manager (keyed by chat_id). Stores last 5 message pairs.
For production, swap the dict for Redis using redis-py with TTL.
"""
from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

TTL_SECONDS = 30 * 60  # 30 minutes

# sessions: {chat_id: {"messages": [...], "last_active": float, "failed_intents": int}}
_sessions: dict[str, dict] = defaultdict(lambda: {
    "messages": [],
    "last_active": time.time(),
    "failed_intents": 0,
})

def get_history(chat_id: str) -> list[dict]:
    _cleanup(chat_id)
    return _sessions[chat_id]["messages"]

def add_message(chat_id: str, role: str, content: str) -> None:
    _cleanup(chat_id)
    sess = _sessions[chat_id]
    sess["messages"].append({"role": role, "content": content})
    # Keep last 10 messages (5 pairs)
    if len(sess["messages"]) > 10:
        sess["messages"] = sess["messages"][-10:]
    sess["last_active"] = time.time()

def increment_failed_intents(chat_id: str) -> int:
    _sessions[chat_id]["failed_intents"] += 1
    return _sessions[chat_id]["failed_intents"]

def reset_failed_intents(chat_id: str) -> None:
    _sessions[chat_id]["failed_intents"] = 0

def get_failed_intents(chat_id: str) -> int:
    return _sessions[chat_id].get("failed_intents", 0)

def _cleanup(chat_id: str) -> None:
    """Expire session if TTL exceeded."""
    sess = _sessions.get(chat_id)
    if sess and (time.time() - sess.get("last_active", 0)) > TTL_SECONDS:
        _sessions[chat_id] = {"messages": [], "last_active": time.time(), "failed_intents": 0}
