"""Сборка роутеров бота."""

from __future__ import annotations

from aiogram import Router

from . import commands, group


def setup_routers() -> Router:
    root = Router(name="root")
    root.include_router(commands.router)  # команды имеют приоритет
    root.include_router(group.router)
    return root
