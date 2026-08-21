from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Settings
from .formatting import (
    daily_ranking_message,
    help_message,
    personal_message,
    weekly_ranking_message,
)
from .periods import period_keys
from .storage import Storage
from .text_rules import dot_command, fingerprint, is_countable_text


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
LOGGER = logging.getLogger(__name__)

DAILY_COMMANDS = {".일일순위"}
WEEKLY_COMMANDS = {".주간순위"}
ME_COMMANDS = {".나"}
HELP_COMMANDS = {".도움말"}


class RankingBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.database_url)

    async def post_init(self, application: Application) -> None:
        if self.storage.connection is None:
            await asyncio.to_thread(self.storage.initialize)
        me = await application.bot.get_me()
        LOGGER.info("Bot started as @%s", me.username)

    async def post_shutdown(self, application: Application) -> None:
        await asyncio.to_thread(self.storage.close)

    async def error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        LOGGER.error("Update handling failed", exc_info=context.error)

    async def handle_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user:
            return
        if chat.type not in {ChatType.GROUP, ChatType.SUPERGROUP}:
            if message.text and message.text.startswith("."):
                await message.reply_text("이 명령어는 소통방 그룹에서 사용해주세요.")
            return

        command = dot_command(message.text or "")
        if command in DAILY_COMMANDS:
            await self.show_daily(update)
            return
        if command in WEEKLY_COMMANDS:
            await self.show_weekly(update)
            return
        if command in ME_COMMANDS:
            await self.show_me(update)
            return
        if command in HELP_COMMANDS:
            await message.reply_text(help_message(), parse_mode=ParseMode.HTML)
            return

        await self.count_message(update)

    async def count_message(self, update: Update) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user or user.is_bot or message.sender_chat:
            return
        if user.id in self.settings.excluded_user_ids:
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

    async def show_daily(self, update: Update) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if not message or not chat:
            return
        keys = period_keys(datetime.now(timezone.utc), self.settings.timezone)
        entries = await asyncio.to_thread(
            self.storage.rankings, chat.id, "day", keys.day_key
        )
        await message.reply_text(
            daily_ranking_message(entries, keys.day_key),
            parse_mode=ParseMode.HTML,
        )

    async def show_weekly(self, update: Update) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if not message or not chat:
            return
        keys = period_keys(datetime.now(timezone.utc), self.settings.timezone)
        entries = await asyncio.to_thread(
            self.storage.rankings, chat.id, "week", keys.week_key
        )
        await message.reply_text(
            weekly_ranking_message(entries, keys.week_key),
            parse_mode=ParseMode.HTML,
        )

    async def show_me(self, update: Update) -> None:
        message = update.effective_message
        chat = update.effective_chat
        user = update.effective_user
        if not message or not chat or not user:
            return
        keys = period_keys(datetime.now(timezone.utc), self.settings.timezone)
        daily, weekly = await asyncio.gather(
            asyncio.to_thread(
                self.storage.personal_rank, chat.id, user.id, "day", keys.day_key
            ),
            asyncio.to_thread(
                self.storage.personal_rank, chat.id, user.id, "week", keys.week_key
            ),
        )
        await message.reply_text(
            personal_message(daily, weekly),
            parse_mode=ParseMode.HTML,
        )


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
    settings = Settings.from_env()
    ranking_bot = RankingBot(settings)
    ranking_bot.storage.initialize()
    application = build_application(settings, ranking_bot)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )
