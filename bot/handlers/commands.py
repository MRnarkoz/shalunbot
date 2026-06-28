"""Служебные команды бота."""

from __future__ import annotations

from aiogram import Router, types
from aiogram.filters import Command

from . import group

router = Router(name="commands")

_HELP = (
    "Я пишу в стиле «Шалуна».\n\n"
    "1) Добавь меня в группу.\n"
    "2) У @BotFather отключи Privacy Mode: /mybots → бот → Bot Settings → "
    "Group Privacy → Turn off (иначе я не вижу обычные сообщения).\n\n"
    "Иногда я сам встреваю в беседу. Чтобы обратиться напрямую — ответь на моё "
    "сообщение, упомяни @меня или позови по имени «Шалун».\n\n"
    "Команды:\n"
    "/shalun — заставить меня ответить прямо сейчас.\n"
    "/summary — выжимка чата с прошлой выжимки (в первый раз — по последним сообщениям)."
)


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer(_HELP)


@router.message(Command("shalun"))
async def cmd_shalun(message: types.Message) -> None:
    group.fire(group.respond(message, addressed=True))


@router.message(Command("summary"))
async def cmd_summary(message: types.Message) -> None:
    group.fire(group.summarize(message))
