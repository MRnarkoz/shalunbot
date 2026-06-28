# shalunbot — Бот Санюка «Шалун»

Telegram-бот, который пишет в стиле участника чата по имени **Шалун**. Ответы
генерирует **DeepSeek** (OpenAI-совместимый API). «Обучение» — не файнтюнинг, а
**персона через системный промпт + few-shot** на реальных фразах Шалуна,
вытащенных из экспорта чата (`messages*.html`).

Бот добавляется в общую группу и **сам, без явных команд, встревает в беседу**
(вероятность + кулдаун), а также отвечает, если к нему обратиться напрямую
(reply, упоминание `@bot` или по имени «Шалун»). Команда `/summary` — выжимка
чата в его стиле.

## Как это работает

```
messages*.html ──(tools/extract_corpus.py)──▶ bot/data/shalun_corpus.json
                                                      │
                                                      ▼
   сообщение в группе ─▶ буфер истории ─▶ решение «влезть?» ─▶ persona+few-shot
                                                      │                  │
                                                      ▼                  ▼
                                              DeepSeek (deepseek-v4-flash) ─▶ ответ
```

- `bot/persona.py` — собирает системный промпт «ты Шалун, вот твои фразы…» +
  несколько примеров «контекст → ответ».
- `bot/handlers/group.py` — на каждое сообщение копит контекст и решает, ответить
  ли: **спонтанно** (`REPLY_PROBABILITY` с учётом `REPLY_COOLDOWN`) или потому что
  **обратились напрямую**.
- `bot/deepseek.py` — async-вызов модели; при ошибке API бот просто молчит.
- История чатов хранится в памяти (перезапуск — начинает копить заново).

## Структура

```
bot/
  __main__.py        точка входа (python -m bot), long polling
  config.py          настройки из .env (pydantic-settings)
  deepseek.py        клиент DeepSeek (AsyncOpenAI на api.deepseek.com)
  persona.py         системный промпт + few-shot из корпуса
  chat_buffer.py     скользящее окно сообщений по чату
  runtime.py         синглтоны persona/buffer
  handlers/
    group.py         спонтанное участие + ответы на обращения
    commands.py      /start, /help, /shalun
  data/
    shalun_corpus.json   корпус фраз Шалуна (сгенерирован)
tools/
  extract_corpus.py  парсер HTML-экспорта -> корпус
Dockerfile, docker-compose.yml, requirements.txt, .env.example
```

## Подготовка в Telegram (важно!)

1. Создай бота у **@BotFather** → `/newbot` → получи **BOT_TOKEN**.
2. **Отключи Privacy Mode** (без этого бот не видит обычные сообщения в группе):
   `/mybots` → выбрать бота → **Bot Settings** → **Group Privacy** → **Turn off**.
   (Альтернатива — сделать бота администратором группы.)
3. Добавь бота в нужную группу.

## DeepSeek

1. Возьми ключ на <https://platform.deepseek.com/> → впиши в `DEEPSEEK_API_KEY`.
2. Модель по умолчанию `deepseek-v4-flash` (дёшево/быстро). Старое имя
   `deepseek-chat` работает до **2026-07-24**, потом только `deepseek-v4-*`.

## Запуск локально

```powershell
# 1. зависимости
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. настройки
copy .env.example .env   # затем впиши BOT_TOKEN и DEEPSEEK_API_KEY

# 3. (опц.) пересобрать корпус из HTML
python tools/extract_corpus.py --target "Шалун" --out bot/data/shalun_corpus.json

# 4. старт
python -m bot
```

## Запуск в Docker / деплой на хост

На сервере (VPS) с Docker:

```bash
git clone <repo> shalunbot && cd shalunbot
cp .env.example .env        # впиши BOT_TOKEN и DEEPSEEK_API_KEY
docker compose up -d --build
docker compose logs -f      # смотреть логи
```

Бот работает на long polling — **публичный IP/домен и проброс портов не нужны**.
`restart: unless-stopped` поднимет его после перезагрузки сервера.

Обновление после изменений: `git pull && docker compose up -d --build`.

## Настройка поведения (`.env`)

| Переменная          | По умолчанию       | Что делает                                   |
|---------------------|--------------------|----------------------------------------------|
| `REPLY_PROBABILITY` | `0.35`             | шанс спонтанно встрять после сообщения        |
| `REPLY_COOLDOWN`    | `40`               | сек между спонтанными вмешательствами в чате   |
| `SUMMARY_FIRST_RUN` | `100`              | сообщений в первой выжимке `/summary`           |
| `CONTEXT_WINDOW`    | `12`               | сколько последних сообщений видит модель        |
| `TEMPERATURE`       | `1.2`              | выше — живее и непредсказуемее                  |
| `TYPING_DELAY`      | `1.5`              | пауза «печатает…» перед ответом, сек            |
| `DEEPSEEK_MODEL`    | `deepseek-v4-flash`| модель DeepSeek                                 |
| `ALLOWED_CHAT_IDS`  | пусто              | ограничить работу чатами (id через запятую)      |

Хочешь, чтобы бот вмешивался чаще — подними `REPLY_PROBABILITY` и/или снизь
`REPLY_COOLDOWN`.

## Команды

- `/help` — краткая справка.
- `/shalun` — заставить бота ответить прямо сейчас по текущему контексту.
- `/summary` — выжимка чата в стиле Шалуна: пересказывает, о чём базарили, с
  прошлой выжимки (в первый раз — по последним сообщениям). **Бот видит только
  то, что пришло после его запуска** — Telegram Bot API не даёт читать историю
  чата, поэтому глубина выжимки ограничена буфером (`BUFFER_SIZE`).

Команды `/start` нет — бот общается сам: спонтанно встревает в беседу
(`REPLY_PROBABILITY` + `REPLY_COOLDOWN`) и отвечает, когда его тегают `@bot`,
зовут по имени «Шалун» или отвечают на его сообщение.

## Обновить «характер»

Положи свежий экспорт чата (`messages*.html`) рядом и перегенерируй корпус:

```bash
python tools/extract_corpus.py --target "Шалун" --out bot/data/shalun_corpus.json
```

Можно сменить имитируемого пользователя через `--target "ДругойНик"` и
`PERSONA_NAME` в `.env`.

---
*Бот имитирует стиль реального участника приватного чата по просьбе его друзей;
лексика соответствует исходному корпусу.*
