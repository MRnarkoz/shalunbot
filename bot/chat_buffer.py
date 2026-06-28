"""Скользящее окно последних сообщений по каждому чату.

Хранится в памяти, но при наличии `STATE_PATH` дублируется на диск, чтобы
история (и, значит, `/summary`) переживала перезапуск бота. Telegram Bot API
не даёт читать историю чата, поэтому бот всё равно видит только то, что пришло
после того, как он впервые оказался в чате запущенным.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict, deque
from pathlib import Path

from .config import settings

log = logging.getLogger(__name__)


class ChatBuffer:
    def __init__(self, maxlen: int | None = None, path: str | None = None) -> None:
        self._maxlen = maxlen or settings.buffer_size
        self._chats: dict[int, deque] = defaultdict(self._new_deque)
        # сколько всего сообщений прошло через чат и где была последняя выжимка —
        # нужно для /summary, чтобы пересказывать только новое
        self._total: dict[int, int] = defaultdict(int)
        self._summary_mark: dict[int, int | None] = defaultdict(lambda: None)

        state = path if path is not None else settings.state_path
        self._path: Path | None = Path(state) if state else None
        self._load()

    def _new_deque(self) -> deque:
        return deque(maxlen=self._maxlen)

    # ---- персистентность ----

    def _load(self) -> None:
        if not self._path or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 — битый файл не должен ронять бота
            log.warning("Не удалось прочитать историю чатов (%s): %s", self._path, exc)
            return
        for cid_str, st in (data.get("chats") or {}).items():
            try:
                cid = int(cid_str)
            except (TypeError, ValueError):
                continue
            dq = self._new_deque()
            for pair in st.get("messages", []):
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    dq.append((pair[0], pair[1]))
            self._chats[cid] = dq
            self._total[cid] = int(st.get("total", len(dq)))
            self._summary_mark[cid] = st.get("mark")

    def _save(self) -> None:
        if not self._path:
            return
        data = {
            "chats": {
                str(cid): {
                    "messages": [[a, t] for a, t in dq],
                    "total": self._total[cid],
                    "mark": self._summary_mark[cid],
                }
                for cid, dq in self._chats.items()
            }
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self._path)  # атомарная замена
        except Exception as exc:  # noqa: BLE001 — сбой записи не критичен для работы
            log.warning("Не удалось сохранить историю чатов (%s): %s", self._path, exc)

    # ---- API ----

    def add(self, chat_id: int, author: str, text: str) -> None:
        text = (text or "").strip()
        if text:
            self._chats[chat_id].append((author, text))
            self._total[chat_id] += 1
            self._save()

    def recent(self, chat_id: int, n: int | None = None) -> list[tuple[str, str]]:
        n = n or settings.context_window
        return list(self._chats[chat_id])[-n:]

    def since_summary(
        self, chat_id: int, first_run_limit: int | None = None
    ) -> list[tuple[str, str]]:
        """Сообщения, накопившиеся с прошлой выжимки.

        Если выжимку для чата ещё не делали — берём последние `first_run_limit`
        сообщений (ограничено глубиной буфера).
        """
        first_run_limit = first_run_limit or settings.summary_first_run
        msgs = list(self._chats[chat_id])
        mark = self._summary_mark[chat_id]
        if mark is None:
            return msgs[-first_run_limit:]
        new_count = self._total[chat_id] - mark
        if new_count <= 0:
            return []
        return msgs[-new_count:] if new_count < len(msgs) else msgs

    def mark_summarized(self, chat_id: int) -> None:
        """Запомнить, что до этого момента выжимка уже сделана."""
        self._summary_mark[chat_id] = self._total[chat_id]
        self._save()
