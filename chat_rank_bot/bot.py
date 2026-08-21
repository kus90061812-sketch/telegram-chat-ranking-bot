from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters

from .config import Settings
from .formatting import personal_message, ranking_message
from .periods import period_keys
from .storage import Storage
from .text_rules import dot_command, fingerprint, is_countable_text


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)

RANKING_COMMANDS = {".채팅순위", ".ranking", ".rank"}
ME_COMMANDS = {".나", ".me"}
HELP_COMMANDS = {".도움말", ".help"}


@dataclass
class CachedAdmins:
    user_ids: set[int]
    expires_at: float


class RankingBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.database_url)
        self.admin_cache: dict[int, CachedAdmins] = {}
        self.registered_chats: set[int] = set()

    async def post_init(self, application: Application) -> None:
        if self.storage.connection is None:
            await asyncio.to_thread(self.storage.initialize)
        me = await application.bot.get_me()
        application.bot_data["bot_username"] = (me.username or "").lower()
        LOGGER.info("Bot started as @%s", me.username)

    async def post_shutdown(self, application: Application) -> None:
        await asyncio.to_thread(self.storage.close)

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        LOGGER.error("Update handling failed", exc_info=context.error)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user:
            return
        if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            if message.text and message.text.startswith("."):
                await message.reply_text("이 명령어는 소통방 그룹에서 사용해주세요.")
            return

        if chat.id not in self.registered_chats:
            await asyncio.to_thread(
                self.storage.register_chat,
                chat.id,
                chat.title or str(chat.id),
                datetime.now(timezone.utc),
            )
            self.registered_chats.add(chat.id)

        command = dot_command(message.text or "")
        if command in RANKING_COMMANDS:
            await self.show_rankings(update)
            return
        if command in ME_COMMANDS:
            await self.show_me(update)
            return
        if command in HELP_COMMANDS:
            await self.show_help(update)
            return

        await self.count_message(update, context)

    async def count_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user or user.is_bot or message.sender_chat:
            return

        text = message.text or message.caption
        if not is_countable_text(text, self.settings.min_text_length):
            return

        sent_at = message.date.astimezone(timezone.utc)
        await asyncio.to_thread(
            self.storage.update_profile,
            chat.id,
            user.id,
            user.full_name,
            user.username,
            sent_at,
        )

        if self.settings.exclude_admins and await self._is_admin(chat.id, user.id, context):
            return

        keys = period_keys(sent_at, self.settings.timezone)
        await asyncio.to_thread(
            self.storage.add_message,
            chat_id=chat.id,
            message_id=message.message_id,
            user_id=user.id,
            sent_at=sent_at,
            day_key=keys.day_key,
            week_key=keys.week_key,
            content_hash=fingerprint(text),
            min_interval_seconds=self.settings.min_message_interval_seconds,
            duplicate_window_seconds=self.settings.duplicate_window_seconds,
        )

    async def show_rankings(self, update: Update) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if not message or not chat:
            return
        now = datetime.now(timezone.utc)
        keys = period_keys(now, self.settings.timezone)
        daily, weekly, ui_settings = await asyncio.gather(
            asyncio.to_thread(self.storage.rankings, chat.id, "day", keys.day_key),
            asyncio.to_thread(self.storage.rankings, chat.id, "week", keys.week_key),
            asyncio.to_thread(self.storage.get_chat_settings, chat.id),
        )
        await message.reply_text(
            ranking_message(daily, weekly, keys.day_key, keys.week_key, ui_settings),
            parse_mode=ParseMode.HTML,
        )

    async def show_me(self, update: Update) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user:
            return
        now = datetime.now(timezone.utc)
        keys = period_keys(now, self.settings.timezone)
        daily, weekly, ui_settings = await asyncio.gather(
            asyncio.to_thread(self.storage.personal_rank, chat.id, user.id, "day", keys.day_key),
            asyncio.to_thread(self.storage.personal_rank, chat.id, user.id, "week", keys.week_key),
            asyncio.to_thread(self.storage.get_chat_settings, chat.id),
        )
        await message.reply_text(
            personal_message(
                user.full_name, daily, weekly, keys.day_key, keys.week_key, ui_settings
            ),
            parse_mode=ParseMode.HTML,
        )

    async def show_help(self, update: Update) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if not message or not chat:
            return
        ui_settings = await asyncio.to_thread(self.storage.get_chat_settings, chat.id)
        await message.reply_text(
            "💬 <b>채팅 순위 봇</b>\n\n"
            ".채팅순위 — 오늘·이번 주 TOP 순위\n"
            ".나 — 내 일간·주간 채팅 수와 순위\n\n"
            f"{escape(ui_settings.help_message)}",
            parse_mode=ParseMode.HTML,
        )

    async def _is_admin(
        self, chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE
    ) -> bool:
        now = time.monotonic()
        cached = self.admin_cache.get(chat_id)
        if not cached or cached.expires_at <= now:
            try:
                administrators = await context.bot.get_chat_administrators(chat_id)
                cached = CachedAdmins(
                    {member.user.id for member in administrators},
                    now + self.settings.admin_cache_seconds,
                )
                self.admin_cache[chat_id] = cached
            except Exception:
                LOGGER.exception("Failed to load administrators for chat %s", chat_id)
                return False
        return user_id in cached.user_ids

def build_application(
    settings: Settings, ranking_bot: RankingBot | None = None
) -> Application:
    ranking_bot = ranking_bot or RankingBot(settings)
    application = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .post_init(ranking_bot.post_init)
        .post_shutdown(ranking_bot.post_shutdown)
        .build()
    )
    application.add_handler(MessageHandler(filters.ALL, ranking_bot.handle_message))
    application.add_error_handler(ranking_bot.error_handler)
    return application


def run() -> None:
    from .web import start_admin_server

    settings = Settings.from_env()
    ranking_bot = RankingBot(settings)
    ranking_bot.storage.initialize()
    start_admin_server(ranking_bot.storage, settings)
    application = build_application(settings, ranking_bot)
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)
