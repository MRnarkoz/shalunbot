"""Извлечение корпуса фраз пользователя из HTML-экспорта Telegram.

Запуск (один раз, офлайн):
    python tools/extract_corpus.py --target "Шалун" --out bot/data/shalun_corpus.json

Результат — JSON:
    {
      "persona": "Шалун",
      "stats": {...},
      "lines": ["...", ...],            # уникальные фразы целевого пользователя
      "dialogues": [                     # примеры "контекст -> ответ" с адресатом
        {"addressee": "Колян", "context": [["Автор", "текст"], ...], "reply": "..."},
        ...
      ]
    }

Адресат (addressee) — кому именно Шалун отвечал: берётся из «In reply to …»
(если есть), иначе — автор предыдущего сообщения. Это позволяет боту повторять
манеру общения Шалуна с конкретным человеком.

Парсер использует только стандартную библиотеку (html.parser). Telegram-экспорт:
    <div class="message default ..." id="message12345"> -> новое сообщение (+ <div class="from_name">)
    <div class="message default ... joined">             -> продолжение того же автора
    <div class="message service">                         -> служебное (дата) — пропускаем
    текст         -> <div class="text">...</div>
    ответ на кого -> <div class="reply_to ..."><a href="...#go_to_message12300">
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import Counter
from html.parser import HTMLParser


class TelegramExportParser(HTMLParser):
    """Потоковый парсер: собирает список сообщений {id, author, text, reply_to}."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.messages: list[dict] = []
        self._cur: dict | None = None
        self._current_author: str | None = None

        self._div_depth = 0
        self._in_from = False
        self._from_depth = 0
        self._from_buf: list[str] = []
        self._in_text = False
        self._text_depth = 0
        self._text_buf: list[str] = []
        self._in_reply = False
        self._reply_depth = 0

    @staticmethod
    def _classes(attrs) -> list[str]:
        for name, value in attrs:
            if name == "class" and value:
                return value.split()
        return []

    @staticmethod
    def _msg_id(attrs) -> int | None:
        for name, value in attrs:
            if name == "id" and value:
                m = re.search(r"(\d+)", value)
                return int(m.group(1)) if m else None
        return None

    def handle_starttag(self, tag: str, attrs):  # noqa: D102
        if tag == "a":
            if self._cur is not None and self._in_reply and self._cur.get("reply_to") is None:
                href = dict(attrs).get("href", "") or ""
                m = re.search(r"go_to_message(\d+)", href)
                if m:
                    self._cur["reply_to"] = int(m.group(1))
            return
        if tag != "div":
            return

        self._div_depth += 1
        classes = self._classes(attrs)

        if "message" in classes:
            self._finalize()
            self._cur = {
                "id": self._msg_id(attrs),
                "author": self._current_author,  # carryover для joined
                "text": "",
                "reply_to": None,
                "service": "service" in classes,
            }
            return
        if "from_name" in classes and not self._in_text:
            self._in_from = True
            self._from_depth = self._div_depth
            self._from_buf = []
        elif classes == ["text"]:
            self._in_text = True
            self._text_depth = self._div_depth
            self._text_buf = []
        elif "reply_to" in classes:
            self._in_reply = True
            self._reply_depth = self._div_depth

    def handle_endtag(self, tag: str):  # noqa: D102
        if tag != "div":
            return
        if self._in_from and self._div_depth == self._from_depth:
            author = "".join(self._from_buf).strip()
            if author:
                self._current_author = author
                if self._cur is not None:
                    self._cur["author"] = author
            self._in_from = False
        if self._in_text and self._div_depth == self._text_depth:
            text = _clean("".join(self._text_buf))
            if self._cur is not None and text:
                self._cur["text"] = (self._cur["text"] + "\n" + text).strip() if self._cur["text"] else text
            self._in_text = False
        if self._in_reply and self._div_depth == self._reply_depth:
            self._in_reply = False
        self._div_depth -= 1

    def handle_data(self, data: str):  # noqa: D102
        if self._in_from:
            self._from_buf.append(data)
        elif self._in_text:
            self._text_buf.append(data)

    def _finalize(self) -> None:
        if self._cur is not None:
            self.messages.append(self._cur)
            self._cur = None

    def close(self):  # noqa: D102
        super().close()
        self._finalize()


def _clean(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def parse_files(paths: list[str]) -> list[dict]:
    messages: list[dict] = []
    for path in paths:
        parser = TelegramExportParser()
        with open(path, encoding="utf-8") as fh:
            parser.feed(fh.read())
        parser.close()
        messages.extend(parser.messages)
    return messages


def build_corpus(messages: list[dict], target: str, context_size: int = 4):
    id_author = {m["id"]: m["author"] for m in messages if m.get("id") and m.get("author")}
    # только текстовые непустые сообщения, в порядке появления
    seq = [m for m in messages if m.get("text") and m.get("author") and not m.get("service")]

    lines: list[str] = []
    seen: set[str] = set()
    dialogues: list[dict] = []
    total_target = 0

    def _add_line(text: str) -> None:
        key = text.lower()
        if key and key not in seen and len(text) <= 400:
            seen.add(key)
            lines.append(text)

    i = 0
    n = len(seq)
    while i < n:
        if seq[i]["author"] != target:
            i += 1
            continue

        # серия идущих подряд сообщений Шалуна — это одна реплика (он часто
        # дробит мысль на несколько сообщений); склеиваем её, чтобы примеры были
        # разной длины: и в одну фразу, и в несколько строк
        run = []
        k = i
        while k < n and seq[k]["author"] == target:
            run.append(seq[k])
            k += 1
        total_target += len(run)

        reply = "\n".join(x["text"] for x in run).strip()
        for x in run:
            _add_line(x["text"])           # отдельные короткие фразы — в пул примеров
        if len(run) > 1:
            _add_line(reply)               # и сама склейка (длинный пример)

        # контекст: предыдущие сообщения до прошлой реплики самого Шалуна
        context: list[list[str]] = []
        j = i - 1
        while j >= 0 and len(context) < context_size:
            prev = seq[j]
            if prev["author"] == target:
                break
            context.insert(0, [prev["author"], prev["text"]])
            j -= 1

        # адресат: по reply_to первого сообщения серии, иначе автор предыдущего
        addressee = None
        rt = run[0].get("reply_to")
        if rt and id_author.get(rt) and id_author[rt] != target:
            addressee = id_author[rt]
        if addressee is None and context:
            addressee = context[-1][0]

        if (context or addressee) and reply:
            dialogues.append({"addressee": addressee, "context": context, "reply": reply})

        i = k

    return lines, dialogues, total_target


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="Шалун")
    ap.add_argument("--glob", default="messages*.html")
    ap.add_argument("--out", default="bot/data/shalun_corpus.json")
    ap.add_argument("--context", type=int, default=4)
    args = ap.parse_args()

    paths = sorted(glob.glob(args.glob), key=_natural_key)
    if not paths:
        raise SystemExit(f"Не найдено файлов по маске {args.glob!r}")

    messages = parse_files(paths)
    lines, dialogues, total = build_corpus(messages, args.target, args.context)

    addr_counts = Counter(d["addressee"] for d in dialogues if d.get("addressee"))
    corpus = {
        "persona": args.target,
        "stats": {
            "source_files": paths,
            "total_messages_parsed": len(messages),
            "target_messages": total,
            "unique_lines": len(lines),
            "dialogue_examples": len(dialogues),
            "dialogues_with_addressee": sum(1 for d in dialogues if d.get("addressee")),
            "top_addressees": addr_counts.most_common(10),
        },
        "lines": lines,
        "dialogues": dialogues,
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(corpus, fh, ensure_ascii=False, indent=2)

    print(json.dumps(corpus["stats"], ensure_ascii=False, indent=2))


def _natural_key(path: str):
    nums = re.findall(r"\d+", os.path.basename(path))
    return [int(n) for n in nums] if nums else [0]


if __name__ == "__main__":
    main()
