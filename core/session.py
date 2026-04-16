"""
Session manager for tracking user UI state across multi-step interactions.
Uses in-memory storage (no DB needed – Telegram bot is single-process).

QoL features:
  - Auto-expire stale FSM states after 5 minutes of inactivity
  - Track last activity timestamp per user
  - Navigation history (breadcrumb back-tracking)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

FSM_TIMEOUT = 300  # 5 minutes — auto-clear stale FSM wizards


@dataclass
class UserSession:
    user_id: int
    state: str = "idle"                        # Current FSM state
    data: dict = field(default_factory=dict)   # Step accumulator
    page: int = 0                              # Current page for paginated views
    active_router: str = ""                    # Currently selected router alias
    language: str = "en"                       # UI language
    log_task: Optional[asyncio.Task] = None    # Running log stream task
    last_activity: float = 0.0                 # Timestamp of last interaction
    nav_stack: list = field(default_factory=list)  # Navigation breadcrumb stack


class SessionManager:

    def __init__(self):
        self._sessions: dict[int, UserSession] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    def get(self, user_id: int) -> UserSession:
        if user_id not in self._sessions:
            self._sessions[user_id] = UserSession(user_id=user_id)
        s = self._sessions[user_id]
        s.last_activity = time.time()
        return s

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
        s.nav_stack.clear()

    def update_data(self, user_id: int, **kwargs):
        s = self.get(user_id)
        s.data.update(kwargs)

    def get_state(self, user_id: int) -> str:
        s = self.get(user_id)
        # Auto-expire check
        if s.state != "idle" and (time.time() - s.last_activity) > FSM_TIMEOUT:
            s.state = "idle"
            s.data = {}
        return s.state

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

    # ── Navigation Stack ──────────────────────────────────────────────────────

    def push_nav(self, user_id: int, callback_data: str):
        """Push current location onto the nav stack (for breadcrumb back)."""
        s = self.get(user_id)
        if len(s.nav_stack) > 10:
            s.nav_stack = s.nav_stack[-10:]  # Prevent unbounded growth
        s.nav_stack.append(callback_data)

    def pop_nav(self, user_id: int) -> str:
        """Pop the last location from nav stack. Returns 'menu:main' if empty."""
        s = self.get(user_id)
        if s.nav_stack:
            return s.nav_stack.pop()
        return "menu:main"

    # ── Log Stream ────────────────────────────────────────────────────────────

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

    # ── Background Cleanup ────────────────────────────────────────────────────

    async def start_cleanup_loop(self):
        """Start background task that clears stale FSM states every 60s."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_loop(self):
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def _cleanup_loop(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()
            expired = []
            for uid, s in self._sessions.items():
                if s.state != "idle" and (now - s.last_activity) > FSM_TIMEOUT:
                    expired.append(uid)
            for uid in expired:
                self._sessions[uid].state = "idle"
                self._sessions[uid].data = {}

    # ── Stats ─────────────────────────────────────────────────────────────────

    def active_count(self) -> int:
        """Number of users with active (non-idle) sessions."""
        return sum(1 for s in self._sessions.values() if s.state != "idle")

    def total_count(self) -> int:
        """Total sessions tracked."""
        return len(self._sessions)
