"""
Log streamer – streams RouterOS logs to a Telegram chat in real time.
Uses /log/print follow=yes under the hood.

CHANGES vs original:
  - asyncio.get_event_loop() replaced with asyncio.get_running_loop()
    (get_event_loop() is deprecated since Python 3.10)
"""

import asyncio
import logging
from aiogram import Bot

log = logging.getLogger("LogStreamer")

TOPIC_EMOJI = {
    "error": "🔴",
    "critical": "🆘",
    "warning": "🟡",
    "info": "🔵",
    "debug": "⚪",
    "firewall": "🛡",
    "dhcp": "📡",
    "wireless": "📶",
    "system": "⚙️",
    "script": "📜",
    "pppoe": "🔗",
    "l2tp": "🔗",
    "ovpn": "🔒",
    "wireguard": "🔒",
    "bgp": "🗺",
    "ospf": "🗺",
    "account": "👤",
    "ntp": "🕐",
    "dns": "🌐",
    "web-proxy": "🌐",
    "hotspot": "📡",
}

MAX_BATCH_SIZE = 10
BATCH_TIMEOUT = 5.0


def _format_log_entry(entry: dict) -> str:
    time_ = entry.get("time", "")
    topics = entry.get("topics", "")
    message = entry.get("message", "")
    topic_list = [t.strip() for t in topics.split(",")]
    emoji = next((TOPIC_EMOJI[t] for t in topic_list if t in TOPIC_EMOJI), "📋")
    return f"{emoji} `{time_}` [{topics}]\n   {message}"


async def stream_logs_to_chat(
    router,
    bot: Bot,
    chat_id: int,
    topics: str = "",
    stop_event: asyncio.Event | None = None,
) -> None:
    """
    Stream logs from router to chat_id.
    Stops when stop_event is set or task is cancelled.
    """
    if stop_event is None:
        stop_event = asyncio.Event()

    batch: list[str] = []
    loop = asyncio.get_running_loop()   # was: get_event_loop() — deprecated since 3.10
    last_flush = loop.time()

    try:
        await bot.send_message(
            chat_id,
            f"📡 *Log stream started*{f' (filter: {topics})' if topics else ''}\n"
            "Send /stop\\_logs to stop.",
            parse_mode="Markdown",
        )

        async for entry in router.stream_logs(topics=topics):
            if stop_event.is_set():
                break

            line = _format_log_entry(entry)
            batch.append(line)

            now = loop.time()
            if len(batch) >= MAX_BATCH_SIZE or (now - last_flush) >= BATCH_TIMEOUT:
                await _flush(bot, chat_id, batch)
                batch = []
                last_flush = now

    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.warning(f"Log stream error: {e}")
    finally:
        if batch:
            await _flush(bot, chat_id, batch)
        try:
            await bot.send_message(chat_id, "🔴 *Log stream stopped.*", parse_mode="Markdown")
        except Exception:
            pass


async def _flush(bot: Bot, chat_id: int, lines: list[str]) -> None:
    text = "\n\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n…"
    try:
        await bot.send_message(chat_id, text, parse_mode="Markdown")
    except Exception as e:
        log.warning(f"Failed to send log batch: {e}")
