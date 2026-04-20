"""
Handler package — registers all domain sub-routers on a parent router
with middleware stack:
  1. ErrorHandlerMiddleware  — catches all exceptions, shows friendly errors
  2. ThrottleMiddleware      — anti-flood, 0.5s cooldown per user  
  3. CallbackAuthMiddleware  — bootstrap + reject unknown users
"""

from aiogram import Router

from handlers import context
from handlers.context import (
    CallbackAuthMiddleware, MessageAuthMiddleware,
    ErrorHandlerMiddleware, ThrottleMiddleware,
)

# Import domain routers
from handlers.commands import router as commands_router
from handlers.fsm import router as fsm_router
from handlers.system import router as system_router
from handlers.interfaces import router as interfaces_router
from handlers.firewall import router as firewall_router
from handlers.dhcp import router as dhcp_router
from handlers.dhcp_guard import router as dhcp_guard_router
from handlers.wireless import router as wireless_router
from handlers.vpn import router as vpn_router
from handlers.files import router as files_router
from handlers.logs import router as logs_router
from handlers.network import router as network_router
from handlers.tools import router as tools_router
from handlers.admin import router as admin_router
from handlers.extras import router as extras_router
from handlers.qol import router as qol_router


# Parent router — all sub-routers are nested here.
parent_router = Router(name="main")


def setup(
    router_manager,
    rbac_manager,
    session_manager,
    bot_instance,
    guard_store=None,
    guard_detector=None,
):
    """Inject dependencies and wire sub-routers."""
    context.init(
        router_manager, rbac_manager, session_manager, bot_instance,
        guard_store, guard_detector,
    )

    # Middleware stack (execution order: first registered → runs first)
    # 1. Error handler — outermost, catches everything
    parent_router.callback_query.middleware(ErrorHandlerMiddleware())
    parent_router.message.middleware(ErrorHandlerMiddleware())
    # 2. Throttle — drops spam before auth even runs
    parent_router.callback_query.middleware(ThrottleMiddleware(cooldown=0.5))
    # 3. Auth — bootstrap + reject unknown users
    parent_router.callback_query.middleware(CallbackAuthMiddleware())
    parent_router.message.middleware(MessageAuthMiddleware())

    # Include sub-routers (order matters: specific before generic)
    parent_router.include_router(commands_router)
    parent_router.include_router(system_router)
    parent_router.include_router(interfaces_router)
    parent_router.include_router(firewall_router)
    parent_router.include_router(dhcp_router)
    parent_router.include_router(dhcp_guard_router)
    parent_router.include_router(wireless_router)
    parent_router.include_router(vpn_router)
    parent_router.include_router(files_router)
    parent_router.include_router(logs_router)
    parent_router.include_router(network_router)
    parent_router.include_router(tools_router)
    parent_router.include_router(admin_router)
    parent_router.include_router(extras_router)
    parent_router.include_router(qol_router)

    # FSM last — catches remaining F.text messages
    parent_router.include_router(fsm_router)
