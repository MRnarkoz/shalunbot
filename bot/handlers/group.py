"""Главный хендлер: буферизуем сообщения и решаем, когда влезть в беседу."""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time

from aiogram import F, Router, types

from .. import deepseek
from ..config import settings
from ..runtime import buffer, persona

log = logging.getLogger(__name__)
router = Router(name="group")

# время последнего спонтанного ответа по чату (для кулдауна)
_last_spontaneous: dict[int, float] = {}
# чаты, для которых прямо сейчас генерится ответ (защита от дублей)
_busy: set[int] = set()
# ссылки на фоновые задачи, чтобы их не собрал GC
_bg_tasks: set[asyncio.Task] = set()

_CHAT_TYPES = {"private", "group", "supergroup"}
_QUOTES_OPEN = "\"'«“"
_QUOTES_CLOSE = "\"'»”"


def fire(coro) -> None:
    """Запустить генерацию ответа в фоне, не блокируя обработку апдейтов."""
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


def _display_name(user: types.User | None) -> str:
    if user is None:
        return "Аноним"
    return user.full_name or user.username or "Аноним"


def _is_addressed(message: types.Message, bot_username: str | None) -> bool:
    """Обратились ли к боту напрямую: reply на его сообщение / @упоминание / по имени."""
    reply = message.reply_to_message
    if reply and reply.from_user and message.bot and reply.from_user.id == message.bot.id:
        return True

    bot_id = message.bot.id if message.bot else None
    # @упоминание или text_mention через сущности (надёжнее, чем поиск по строке)
    for ent in message.entities or []:
        if ent.type == "text_mention" and ent.user and bot_id and ent.user.id == bot_id:
            return True
        if ent.type == "mention" and bot_username:
            mention = (message.text or "")[ent.offset : ent.offset + ent.length]
            if mention.lower() == f"@{bot_username.lower()}":
                return True

    text = (message.text or "").lower()
    if bot_username and f"@{bot_username.lower()}" in text:  # на всякий случай и по тексту
        return True
    if settings.persona_name.lower() in text:  # позвали по имени «Шалун»
        return True
    return False


def _should_jump_in(chat_id: int) -> bool:
    """Спонтанное вмешательство: вероятность + кулдаун (никаких явных триггеров)."""
    now = time.monotonic()
    if now - _last_spontaneous.get(chat_id, 0.0) < settings.reply_cooldown:
        return False
    return random.random() < settings.reply_probability


def _cleanup(text: str) -> str:
    text = text.strip()
    if len(text) >= 2 and text[0] in _QUOTES_OPEN and text[-1] in _QUOTES_CLOSE:
        text = text[1:-1].strip()
    # убрать возможный префикс "Шалун:" если модель его добавила
    text = re.sub(rf"^{re.escape(settings.persona_name)}\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


async def respond(message: types.Message, addressed: bool) -> None:
    """Сгенерировать и отправить реплику в стиле Шалуна."""
    chat_id = message.chat.id
    if chat_id in _busy:  # уже готовим ответ для этого чата — не дублируем
        return
    _busy.add(chat_id)  # атомарно в рамках event loop (между check и add нет await)
    try:
        # адресат — тот, кто сейчас пишет: отвечаем ему в манере Шалуна именно с ним
        addressee = _display_name(message.from_user)
        payload = persona.build_messages(
            persona.format_transcript(buffer.recent(chat_id)), addressee=addressee
        )

        try:
            await message.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:  # noqa: BLE001 — индикатор «печатает» не критичен
            pass
        if settings.typing_delay > 0:
            await asyncio.sleep(settings.typing_delay)

        reply = await deepseek.complete(payload)
        if not reply:
            return
        reply = _cleanup(reply)
        if not reply:
            return

        is_private = message.chat.type == "private"
        try:
            if addressed and not is_private:
                await message.reply(reply)
            else:
                await message.answer(reply)
        except Exception as exc:  # noqa: BLE001 — сообщение могли удалить и т.п.
            log.warning("Не удалось отправить ответ: %s", exc)
            return

        buffer.add(chat_id, settings.persona_name, reply)
        _last_spontaneous[chat_id] = time.monotonic()
    finally:
        _busy.discard(chat_id)


async def summarize(message: types.Message) -> None:
    """Сделать выжимку чата с прошлой выжимки (в первый раз — последних сообщений)."""
    chat_id = message.chat.id
    if chat_id in _busy:  # уже что-то генерим для этого чата — не дублируем
        return
    _busy.add(chat_id)
    try:
        msgs = buffer.since_summary(chat_id)
        if not msgs:
            await message.answer("да базарить не о чем, тишина как в пустом депозите")
            return

        payload = persona.build_summary_messages(persona.format_transcript(msgs))
        try:
            await message.bot.send_chat_action(chat_id=chat_id, action="typing")
        except Exception:  # noqa: BLE001 — индикатор «печатает» не критичен
            pass

        reply = await deepseek.complete(
            payload,
            temperature=settings.summary_temperature,
            max_tokens=settings.summary_max_tokens,
        )
        if not reply:
            return
        reply = _cleanup(reply)
        if not reply:
            return

        try:
            await message.answer(reply)
        except Exception as exc:  # noqa: BLE001 — сообщение могли удалить и т.п.
            log.warning("Не удалось отправить выжимку: %s", exc)
            return

        # двигаем точку «последней выжимки»; саму выжимку в буфер не кладём
        buffer.mark_summarized(chat_id)
    finally:
        _busy.discard(chat_id)


@router.message(F.text & ~F.text.startswith("/"), F.chat.type.in_(_CHAT_TYPES))
async def on_message(message: types.Message, bot_username: str | None = None) -> None:
    chat_id = message.chat.id
    if settings.allowed_chats and chat_id not in settings.allowed_chats:
        return

    buffer.add(chat_id, _display_name(message.from_user), message.text or "")

    if message.from_user and message.from_user.is_bot:
        return  # не отвечаем другим ботам — защита от петель

    is_private = message.chat.type == "private"
    addressed = is_private or _is_addressed(message, bot_username)
    if not addressed and not _should_jump_in(chat_id):
        return

    _last_spontaneous[chat_id] = time.monotonic()  # ставим кулдаун сразу при решении
    fire(respond(message, addressed))
