"""Конфигурация бота (читается из переменных окружения / .env)."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Telegram ---
    bot_token: str  # токен от @BotFather (обязательно)

    # --- DeepSeek (OpenAI-совместимый API) ---
    deepseek_api_key: str  # ключ с platform.deepseek.com (обязательно)
    deepseek_base_url: str = "https://api.deepseek.com"
    # deepseek-v4-flash — дёшево/быстро (нужный режим для болталки).
    # Старое имя deepseek-chat работает до 2026-07-24.
    deepseek_model: str = "deepseek-v4-flash"
    temperature: float = 1.0          # живо, но не настолько, чтобы лепить ответ не в тему
    max_tokens: int = 700             # хватает и на длинную реплику в несколько предложений
    request_timeout: float = 40.0

    # --- Персона и поведение ---
    persona_name: str = "Шалун"
    reply_probability: float = 0.35   # шанс спонтанно встрять после сообщения (без тегов)
    reply_cooldown: int = 40          # сек между спонтанными вмешательствами в одном чате
    context_window: int = 20          # сколько последних сообщений отдаём модели (нить разговора)
    buffer_size: int = 120            # глубина буфера истории на чат (хватает на /summary)
    few_shot_examples: int = 40       # фраз-примеров в системном промпте (часть — под собеседника)
    dialogue_shots: int = 6           # диалоговых примеров «контекст→ответ» (приоритет — собеседник)
    typing_delay: float = 1.5         # пауза с «печатает…» перед ответом, сек

    # --- /summary — выжимка чата в стиле Шалуна ---
    summary_first_run: int = 100      # сколько последних сообщений берём, если саммари ещё не делали
    summary_max_tokens: int = 700     # выжимка длиннее обычной реплики
    summary_temperature: float = 1.0  # чуть ровнее, чтобы пересказ был связным

    # Куда сохранять историю чатов, чтобы /summary пережил перезапуск/пересборку.
    # В Docker сюда смонтирован volume (см. docker-compose.yml).
    # Пусто = не сохранять (история только в памяти, теряется при рестарте).
    state_path: str = "state/chat_state.json"

    # Ограничить работу конкретными чатами (id через запятую). Пусто = во всех.
    allowed_chat_ids: str = ""

    @property
    def allowed_chats(self) -> set[int]:
        return {
            int(x) for x in self.allowed_chat_ids.replace(" ", "").split(",") if x
        }


settings = Settings()
