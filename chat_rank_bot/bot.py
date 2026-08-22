from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress
from datetime import datetime, timezone

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.error import TelegramError
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
from .health import start_health_server
from .periods import period_keys
from .picks import (
    custom_emoji_prefix_html,
    parse_slash_command,
    pick_message_html,
)
from .storage import Storage
from .text_rules import dot_command, fingerprint, is_countable_text


logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

DAILY_COMMANDS = {".일일순위"}
WEEKLY_COMMANDS = {".주간순위"}
ME_COMMANDS = {".나"}
HELP_COMMANDS = {".도움말"}
PICK_PREFIX_SETTING = "pick_prefix_html"


class RankingBot:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = Storage(settings.database_url)
        self.registered_chats: set[int] = set()
        self.broadcast_task: asyncio.Task[None] | None = None

    async def post_init(self, application: Application) -> None:
        if self.storage.connection is None:
            await asyncio.to_thread(self.storage.initialize)
        self.registered_chats.update(
            await asyncio.to_thread(self.storage.list_chat_ids)
        )
        me = await application.bot.get_me()
        LOGGER.info("Bot started as @%s", me.username)
        LOGGER.info(
            "Weekly ranking auto-send interval: every %s hour(s)",
            self.settings.weekly_broadcast_interval_hours,
        )
        self.broadcast_task = asyncio.create_task(
            self.scheduled_weekly_broadcast(application),
            name="scheduled-weekly-ranking",
        )

    async def post_shutdown(self, application: Application) -> None:
        if self.broadcast_task:
            self.broadcast_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.broadcast_task
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
        if chat.type == ChatType.PRIVATE:
            await self.handle_private_message(update, context)
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

    async def handle_private_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        message = update.effective_message
        user = update.effective_user
        if not message or not user or not message.text:
            return

        text = message.text
        if parse_slash_command(text, "내아이디") is not None:
            await message.reply_text(f"내 텔레그램 고유번호: {user.id}")
            return

        emoji_command = parse_slash_command(text, "픽이모지설정")
        pick_command = parse_slash_command(text, "픽")
        if emoji_command is None and pick_command is None:
            return
        if not await self.check_pick_admin(message, user.id):
            return

        if emoji_command is not None:
            await self.save_pick_emoji(message)
            return
        await self.send_pick_to_all_groups(message, context, pick_command.argument)

    async def check_pick_admin(self, message, user_id: int) -> bool:
        if not self.settings.pick_admin_user_ids:
            await message.reply_text(
                "PICK_ADMIN_USER_IDS가 설정되지 않았습니다.\n"
                f"Railway Variables에 PICK_ADMIN_USER_IDS={user_id} 를 추가하고 "
                "재배포해주세요."
            )
            return False
        if user_id not in self.settings.pick_admin_user_ids:
            await message.reply_text("픽 전송 권한이 없습니다.")
            return False
        return True

    async def save_pick_emoji(self, message) -> None:
        try:
            prefix_html = custom_emoji_prefix_html(
                message.text,
                message.entities or (),
            )
        except ValueError as exc:
            await message.reply_text(
                f"{exc}\n\n사용법: /픽이모지설정 [프리미엄 이모지]"
            )
            return

        await asyncio.to_thread(
            self.storage.set_setting,
            PICK_PREFIX_SETTING,
            prefix_html,
        )
        try:
            await message.reply_text(
                f"{prefix_html}\n\n고정 프리미엄 이모지 저장 완료",
                parse_mode=ParseMode.HTML,
            )
        except TelegramError:
            await asyncio.to_thread(
                self.storage.delete_setting,
                PICK_PREFIX_SETTING,
            )
            LOGGER.exception("Failed to validate the pick custom emoji")
            await message.reply_text(
                "프리미엄 이모지를 봇이 전송하지 못했습니다.\n"
                "이 봇을 만든 텔레그램 계정의 Premium 구독을 확인해주세요."
            )

    async def send_pick_to_all_groups(
        self,
        message,
        context: ContextTypes.DEFAULT_TYPE,
        content: str,
    ) -> None:
        if not content:
            await message.reply_text("사용법: /픽 [전송할 내용]")
            return

        prefix_html = await asyncio.to_thread(
            self.storage.get_setting,
            PICK_PREFIX_SETTING,
        )
        if not prefix_html:
            await message.reply_text(
                "먼저 /픽이모지설정 [프리미엄 이모지] 를 보내주세요."
            )
            return

        chat_ids = await asyncio.to_thread(self.storage.list_chat_ids)
        if not chat_ids:
            await message.reply_text(
                "등록된 소통방이 없습니다. 소통방에서 봇에게 채팅을 한 번 보내주세요."
            )
            return

        outgoing = pick_message_html(prefix_html, content)
        succeeded = 0
        failed = 0
        for index, chat_id in enumerate(chat_ids):
            try:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=outgoing,
                    parse_mode=ParseMode.HTML,
                )
                succeeded += 1
            except TelegramError:
                failed += 1
                LOGGER.exception("Failed to send pick to chat %s", chat_id)
            if index + 1 < len(chat_ids):
                await asyncio.sleep(0.05)

        await message.reply_text(
            "픽 전송 완료\n"
            f"성공: {succeeded}개\n"
            f"실패: {failed}개"
        )

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

    async def scheduled_weekly_broadcast(self, application: Application) -> None:
        interval_seconds = self.settings.weekly_broadcast_interval_hours * 60 * 60
        while True:
            await asyncio.sleep(interval_seconds)
            await self.broadcast_weekly(application)

    async def broadcast_weekly(self, application: Application) -> None:
        keys = period_keys(datetime.now(timezone.utc), self.settings.timezone)
        chat_ids = await asyncio.to_thread(self.storage.list_chat_ids)
        for chat_id in chat_ids:
            try:
                entries = await asyncio.to_thread(
                    self.storage.rankings,
                    chat_id,
                    "week",
                    keys.week_key,
                )
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=weekly_ranking_message(entries, keys.week_key),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                LOGGER.exception(
                    "Failed to send scheduled weekly ranking to chat %s",
                    chat_id,
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
    health_server = start_health_server(int(os.getenv("PORT", "8000")))
    try:
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=False,
        )
    finally:
        health_server.shutdown()
        health_server.server_close()
