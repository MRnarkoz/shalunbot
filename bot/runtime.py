"""Синглтоны времени выполнения: персона и буфер истории чатов."""

from __future__ import annotations

from .chat_buffer import ChatBuffer
from .persona import Persona

persona = Persona()
buffer = ChatBuffer()
