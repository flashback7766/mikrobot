"""
Connection quality monitor — tests latency and packet loss to router API.
Used by /status and health checks.
"""

import asyncio
import time
import logging
from typing import Optional

log = logging.getLogger("Quality")


async def check_api_latency(router, samples: int = 3) -> dict:
    """
    Measure round-trip latency to the router API.
    Returns: {latency_ms: float, jitter_ms: float, success: bool}
    """
    times = []
    errors = 0
    for _ in range(samples):
        t0 = time.monotonic()
        try:
            await asyncio.wait_for(router.get_system_identity(), timeout=5.0)
            times.append((time.monotonic() - t0) * 1000)
        except Exception:
            errors += 1
        await asyncio.sleep(0.1)

    if not times:
        return {"latency_ms": 0, "jitter_ms": 0, "success": False, "loss_pct": 100}

    avg = sum(times) / len(times)
    jitter = max(times) - min(times) if len(times) > 1 else 0
    loss = int(errors / samples * 100)
    return {"latency_ms": round(avg, 1), "jitter_ms": round(jitter, 1), "success": True, "loss_pct": loss}


def quality_emoji(latency_ms: float, loss_pct: int) -> str:
    """Return signal quality emoji based on latency and loss."""
    if loss_pct > 50 or latency_ms == 0:
        return "💀"
    if loss_pct > 20 or latency_ms > 2000:
        return "🔴"
    if latency_ms > 500:
        return "🟡"
    if latency_ms > 100:
        return "🟢"
    return "⚡"


def fmt_quality(result: dict) -> str:
    emoji = quality_emoji(result["latency_ms"], result["loss_pct"])
    if not result["success"]:
        return "💀 API unreachable"
    return (
        f"{emoji} Latency: `{result['latency_ms']}ms` "
        f"| Jitter: `{result['jitter_ms']}ms` "
        f"| Loss: `{result['loss_pct']}%`"
    )
