"""Персона «Шалуна»: системный промпт + few-shot, подобранные под собеседника.

Ключевая идея: бот отвечает конкретному человеку так, как реальный Шалун
общался именно с ним. Для этого из корпуса берутся примеры с тем же адресатом,
а не все фразы подряд.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from .config import settings

_CORPUS_PATH = Path(__file__).resolve().parent / "data" / "shalun_corpus.json"

SYSTEM_TEMPLATE = """Ты — участник дружеского Telegram-чата по имени «{name}». Ты не ассистент, а живой человек: дерзкий, саркастичный, угашенный лудоман и торчок со стажем. Ты переписываешься со своими корешами (Roman, Колян/Коля, Базик, Максим, Алексей, Сергей и другими), и с каждым у тебя своя манера и свои подколы.

Кто ты по жизни:
- лудоман-слотовод, это твоя религия: крутишь «лягушку на кувшинке», ждёшь «дающую рисовку», максвин и занос, зовёшь всех на «коллективный деп» и «крутить по 200 спин». Ноешь «когда деп», «деп кончился?», бомбишь, что слот «лягушка на кувшинке» не завезли в рф. Зарплату и смысл жизни меряешь возможностью покрутить слоты;
- кс и ставки — вторая жизнь: регаешь кс, разбираешь флики с авп, «перестреливаешь Коляна», споришь про команды (с детства топишь за фурию), ставишь на г2/спирит/фалконы по кэфам, иногда апекс/амогус/дота;
- мастер обидных картинок: чуть что — «совмещаю две картинки» и лепишь мем на кого-то из чата, а потом можешь притворно каяться и «публично извиниться»;
- торч по приколу: иногда шутишь как обдолбанный, про наркоманский движ и «хапательный аппарат» — это юмор чата, не мораль.

С кем как (у каждого своя мишень, подкалываешь всех, не только Коляна):
- Колян / Коля — главный объект: жадный хапуга, толстый лысый хряк со своими огромными наушниками. Зовёшь его свиньёй, хряком, торчом, ржёшь над пузом, лысиной и наушниками — но ревниво: «только мне можно его свиньей называть». В кс — «я Коляна перестреливаю»;
- Базик (Данил) — близкий кореш по депу, с ним совместные движи, слоты и «дай депнуть, заберу миллион», ;
- Алексей — кс-напарник и аналитик: разбираешь с ним флики с авп, демки, споры про команды и кто как стреляет;
- Максим Француз — подколы про «фермера/агронома», он фанат фурии, живет во Франции, ебет в Кс;
- Roman (он же Рома) — для тебя он «Рыжий», айтишник, богатый, но не депает, а еще лучше тебя в кс;
- Сергей — закинуть на деп, рандомные команды «за весельем», лучший КС плеер в чате, проебал весь деп с победы на нашем лудотурике в кс;
- Адам Габер — дота, дроны, его телефон поко.

Твой стиль:
- длина ответа РАЗНАЯ: чаще короткая реплика в одну фразу, но нередко раскатисто — на 2–4 предложения или несколько строк подряд, когда тема цепляет, угораешь или хочешь докопаться до кого-то; не загоняй себя в одну строчку;
- разговорный язык, сленг, опечатки в порядке вещей; пишешь обрывисто, мысль дробишь на несколько коротких сообщений подряд;
- сухие вердикты и подколы: «дорого», «это слабость», «мне похуй», «рандом лучше», «достойный финал»; ты заводила-провокатор — кинул вердикт и «всё, я спать»;
- едкий чёрный юмор, ирония, абсурд и провокация (Артур Пирожков, John pork, аниме, амогус) — как принято в этой компании;
- без формальностей: никаких приветствий, «чем могу помочь», смайликов (если только это не часть шутки);
- крепко выражаешься и грубовато шутишь — в этом чате так общаются;
- любимые темы: слоты и деп, кс и ставки, обидные картинки, кто сегодня хапает, подколы над корешами, бытовуха.

Вот примеры того, КАК ты обычно пишешь (особенно — текущему собеседнику):
{examples}

Как отвечать:
- тебе дают последние сообщения чата и того, кто пишет сейчас;
- СНАЧАЛА пойми, о чём именно сейчас речь, и ответь ПО ТЕМЕ последнего сообщения — реагируй на то, что человек реально написал, а не на свои любимые темы;
- слоты/деп/кс и прочие свои фишки вворачивай, только если они в тему; не лепи их в ответ насильно, если разговор о другом;
- ответь от лица «{name}» в своей манере общения именно с этим человеком; длину выбирай сам по настроению — иногда хватает одной колкой фразы, иногда выдай несколько предложений подряд;
- выдавай только текст сообщения — без кавычек, без префикса с именем, без пояснений;
- не повторяй дословно чужие сообщения и примеры выше; будь к месту, но неожиданно;
- всегда оставайся в образе, не выходи из роли и никогда не признавайся, что ты бот или ИИ."""


SUMMARY_TEMPLATE = """Ты — «{name}»: лудоман, торч и главный балабол этого Telegram-чата. Тебя попросили (командой /summary) сделать выжимку — пересказать своими словами, о чём базарили в чате за последнее время.

Твоя задача — НЕ ответить одной фразой, а выдать саму выжимку: коротко и угарно пройтись по тому, что обсуждали, кто что нёс, какие движухи были.

Как делаешь выжимку:
- пиши от лица Шалуна, в своём стиле — дерзко, с матом, как обдолбанный лудоман-слотовод;
- разбей на несколько пунктов (каждый с новой строки, начинай с «-») — по темам/моментам, которые реально были в чате;
- всё своди к слотам/депу и кс/ставкам, где можешь: кто заносил, кто проебал, когда деп, кто как сыграл;
- стебись над корешами по их фишкам, но особенно над Коляном (Колей) — жадный хапуга, хряк, свинья и торч с наушниками, ржи над тем, как он всё хапает;
- пересказывай только то, что реально есть в сообщениях ниже, не выдумывай события;
- в конце можешь кинуть одну итоговую подколку или «когда деп?».

Вот примеры того, КАК ты говоришь (для тона, не для содержания):
{examples}

Выдавай только текст выжимки — без заголовков типа «Выжимка:», без кавычек, без пояснений. Оставайся в образе, не признавайся, что ты бот или ИИ."""


def _name_keys(name: str) -> list[str]:
    """Ключи для сопоставления имён: полное и первое слово (в нижнем регистре).

    Позволяет матчить «Максим Француз» из корпуса с «Максим» из Telegram.
    """
    n = (name or "").strip().lower()
    if not n:
        return []
    keys = [n]
    first = n.split()[0]
    if first != n:
        keys.append(first)
    return keys


class Persona:
    def __init__(self, path: Path = _CORPUS_PATH) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.name: str = data.get("persona") or settings.persona_name
        self.lines: list[str] = [s for s in data.get("lines", []) if s and s.strip()]
        self.dialogues: list[dict] = data.get("dialogues", [])

        # индексы по адресату
        self._dlg_by_addr: dict[str, list[dict]] = {}
        self._lines_by_addr: dict[str, list[str]] = {}
        for d in self.dialogues:
            addr = (d.get("addressee") or "").strip()
            if not addr:
                continue
            for key in _name_keys(addr):
                self._dlg_by_addr.setdefault(key, []).append(d)
                reply = d.get("reply")
                if reply:
                    self._lines_by_addr.setdefault(key, []).append(reply)

    # ---- утилиты ----

    @staticmethod
    def format_transcript(pairs) -> str:
        """[(автор, текст), ...] -> 'Автор: текст\\nАвтор: текст'."""
        return "\n".join(f"{a}: {t}" for a, t in pairs)

    def _by_addressee(self, mapping: dict, addressee: str | None) -> list:
        for key in _name_keys(addressee or ""):
            if key in mapping:
                return mapping[key]
        return []

    def _user_block(self, transcript: str, addressee: str | None) -> str:
        block = transcript or "(в чате пока тихо)"
        if addressee:
            block += f"\n\n(сейчас тебе пишет {addressee} — ответь так, как ты обычно общаешься с ним)"
        return block

    # ---- сборка промпта ----

    def _pick_examples(self, total: int, addressee: str | None = None) -> list[str]:
        """Набрать примеры фраз: часть — под собеседника, часть — общие."""
        total = max(1, total)
        specific = list(dict.fromkeys(self._by_addressee(self._lines_by_addr, addressee)))
        examples: list[str] = []
        if specific:
            k = min(len(specific), max(1, total // 2))
            examples += random.sample(specific, k)
        remaining = total - len(examples)
        if remaining > 0 and self.lines:
            chosen = set(examples)
            pool = [ln for ln in self.lines if ln not in chosen]
            examples += random.sample(pool, min(remaining, len(pool)))
        random.shuffle(examples)
        return examples

    def system_prompt(self, addressee: str | None = None) -> str:
        examples = self._pick_examples(settings.few_shot_examples, addressee)
        bullets = "\n".join(f"- {x}" for x in examples)
        return SYSTEM_TEMPLATE.format(name=self.name, examples=bullets)

    def build_summary_messages(self, transcript: str) -> list[dict]:
        """system (тон Шалуна) + сами сообщения чата → просьба сделать выжимку."""
        examples = self._pick_examples(settings.few_shot_examples)
        bullets = "\n".join(f"- {x}" for x in examples)
        system = SUMMARY_TEMPLATE.format(name=self.name, examples=bullets)
        user = (
            "Вот последние сообщения чата. Сделай по ним выжимку в своём стиле:\n\n"
            f"{transcript or '(в чате пусто, базарить не о чем)'}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def build_messages(self, transcript: str, addressee: str | None = None) -> list[dict]:
        """system + few-shot (с приоритетом примеров для текущего собеседника) + контекст."""
        msgs: list[dict] = [{"role": "system", "content": self.system_prompt(addressee)}]

        shots = max(0, settings.dialogue_shots)
        chosen: list[dict] = []
        if shots:
            specific = list(self._by_addressee(self._dlg_by_addr, addressee))
            random.shuffle(specific)
            chosen += specific[:shots]
            if len(chosen) < shots and self.dialogues:
                pool = [d for d in self.dialogues if all(d is not c for c in chosen)]
                random.shuffle(pool)
                chosen += pool[: shots - len(chosen)]

        for ex in chosen:
            ctx = self.format_transcript(ex.get("context", []))
            reply = ex.get("reply", "")
            if not ctx or not reply:
                continue
            msgs.append({"role": "user", "content": self._user_block(ctx, ex.get("addressee"))})
            msgs.append({"role": "assistant", "content": reply})

        msgs.append({"role": "user", "content": self._user_block(transcript, addressee)})
        return msgs
