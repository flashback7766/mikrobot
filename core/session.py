"""
Session manager for tracking user UI state across multi-step interactions.
Uses in-memory storage (no DB needed – Telegram bot is single-process).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class UserSession:
    user_id: int
    state: str = "idle"          # Current FSM state
    data: dict = field(default_factory=dict)   # Step accumulator
    page: int = 0                # Current page for paginated views
    active_router: str = ""      # Currently selected router alias
    language: str = "en"         # UI language
    log_task: Optional[asyncio.Task] = None    # Running log stream task


class SessionManager:

    def __init__(self):
        self._sessions: dict[int, UserSession] = {}

    def get(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        return self._sessions[user_id]

    def set_state(self, user_id: int, state: str, data: dict | None = None):
        s = self.get(user_id)
        s.state = state
        if data is not None:
            s.data = data
        # If data is None, preserve existing accumulated data (do not reset)

    def clear_state(self, user_id: int):
        s = self.get(user_id)
        s.state = "idle"
        s.data = {}

    def update_data(self, user_id: int, **kwargs):
        s = self.get(user_id)
        s.data.update(kwargs)

    def get_state(self, user_id: int) -> str:
        return self.get(user_id).state

    def get_data(self, user_id: int) -> dict:
        return self.get(user_id).data

    def set_page(self, user_id: int, page: int):
        self.get(user_id).page = page

    def get_page(self, user_id: int) -> int:
        return self.get(user_id).page

    def set_language(self, user_id: int, lang: str):
        self.get(user_id).language = lang

    def get_language(self, user_id: int) -> str:
        return self.get(user_id).language

    async def stop_log_stream(self, user_id: int):
        s = self.get(user_id)
        if s.log_task and not s.log_task.done():
            s.log_task.cancel()
            try:
                await s.log_task
            except asyncio.CancelledError:
                pass
        s.log_task = None

    def set_log_task(self, user_id: int, task: asyncio.Task):
        self.get(user_id).log_task = task
