"""File handlers: browse, detail, download, delete."""

from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile

from handlers import context as ctx
from handlers.base import send_or_edit, require_router
from ui import keyboards as kb
from ui import formatters as fmt

router = Router()


@router.callback_query(F.data == "menu:files")
async def menu_files(cb: CallbackQuery):
    if not ctx.rbac.can(cb.from_user.id, "file.view"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    files = await r.get_files()
    await send_or_edit(cb, fmt.fmt_files(files), kb.files_menu(files))


@router.callback_query(F.data.startswith("file:detail:"))
async def file_detail(cb: CallbackQuery):
    name = ":".join(cb.data.split(":")[2:])
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    files = await r.get_files()
    f = next((x for x in files if x.get("name") == name), None)
    if not f:
        await cb.answer("File not found.", show_alert=True)
        return
    size = int(f.get("size", 0))
    text = (
        f"📄 *File: {name}*\n"
        f"Size: `{size:,}` bytes\n"
        f"Created: `{f.get('creation-time', '?')}`\n"
        f"Type: `{f.get('type', 'unknown')}`"
    )
    await send_or_edit(cb, text, kb.file_detail_menu(name))


@router.callback_query(F.data.startswith("file:download:"))
async def file_download(cb: CallbackQuery):
    name = ":".join(cb.data.split(":")[2:])
    if not ctx.rbac.can(cb.from_user.id, "file.download"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    try:
        content = await r.get_backup_file(name)
        await cb.answer("⬇️ Preparing download…")
        doc = BufferedInputFile(content, filename=name.split("/")[-1])
        await cb.message.answer_document(doc, caption=f"📄 `{name}`", parse_mode="Markdown")
    except NotImplementedError:
        await cb.answer("⚠️ Download requires FTP access to the router.", show_alert=True)
    except Exception as e:
        await cb.answer(f"❌ Error: {e}", show_alert=True)


@router.callback_query(F.data.startswith("file:delete:"))
async def file_delete(cb: CallbackQuery):
    name = ":".join(cb.data.split(":")[2:])
    if not ctx.rbac.can(cb.from_user.id, "file.delete"):
        await cb.answer("🚫 Insufficient permissions.", show_alert=True)
        return
    r = await require_router(cb, ctx.rm)
    if not r:
        return
    await r.delete_file(name)
    await cb.answer(f"🗑 {name} deleted")
    files = await r.get_files()
    await send_or_edit(cb, fmt.fmt_files(files), kb.files_menu(files))
