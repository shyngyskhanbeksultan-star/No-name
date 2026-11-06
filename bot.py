import asyncio
import json
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ChatMemberStatus
from aiogram.filters import CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.getenv("BOT_TOKEN")

# Каналы для проверки подписки (username без @)
CHANNELS = ["potujno_cheat", "UranCB"]

GREETING = "Привет! Пожалуйста подпишись на автора его канала!"

DATA_FILE = Path(__file__).parent / "data.json"
dp = Dispatcher()


# ---------- хранилище (запоминает файлы из приватного канала) ----------
def load() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {"channel_id": None, "files": []}


def save(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@dp.channel_post(F.document | F.video | F.audio | F.photo | F.animation)
async def on_channel_post(post: Message):
    """Любой файл, который ты кинешь в приватный канал, сам станет кнопкой."""
    data = load()
    if data["channel_id"] is None:
        data["channel_id"] = post.chat.id  # первый канал становится хранилищем
    if post.chat.id != data["channel_id"]:
        return

    media = post.document or post.video or post.audio or post.animation
    title = (post.caption or "").split("\n")[0]
    if not title and media and getattr(media, "file_name", None):
        title = Path(media.file_name).stem
    title = (title or "Файл")[:40]

    data["files"].append({"title": title, "message_id": post.message_id})
    save(data)


# ---------- бот ----------
def keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="1️⃣", url=f"https://t.me/{CHANNELS[0]}")],
            [InlineKeyboardButton(text="2️⃣", url=f"https://t.me/{CHANNELS[1]}")],
            [InlineKeyboardButton(text="✅ Проверить подписку", callback_data="check")],
        ]
    )


def files_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"#{i} {f['title']}", callback_data=f"file:{i - 1}")]
        for i, f in enumerate(load()["files"], start=1)
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    for ch in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=f"@{ch}", user_id=user_id)
        except Exception as e:
            logging.warning("Не удалось проверить @%s: %s", ch, e)
            return False
        if member.status not in (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        ):
            return False
    return True


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(GREETING, reply_markup=keyboard())


@dp.callback_query(F.data == "check")
async def check(call: CallbackQuery, bot: Bot):
    if not await is_subscribed(bot, call.from_user.id):
        await call.answer(
            "Ты ещё не подписался на оба канала! Подпишись и нажми снова.",
            show_alert=True,
        )
        return

    await call.answer()
    if load()["files"]:
        await call.message.answer("Спасибо за подписку!", reply_markup=files_keyboard())
    else:
        await call.message.answer("Спасибо за подписку! Файлы пока не загружены.")


@dp.callback_query(F.data.startswith("file:"))
async def send_file(call: CallbackQuery, bot: Bot):
    if not await is_subscribed(bot, call.from_user.id):
        await call.answer("Сначала подпишись на оба канала!", show_alert=True)
        return

    data = load()
    index = int(call.data.split(":")[1])
    if index >= len(data["files"]):
        await call.answer("Файл не найден.", show_alert=True)
        return

    await call.answer()
    try:
        await bot.copy_message(
            chat_id=call.from_user.id,
            from_chat_id=data["channel_id"],
            message_id=data["files"][index]["message_id"],
        )
    except Exception as e:
        logging.warning("Не удалось отправить файл: %s", e)
        await call.message.answer("Файл недоступен, напиши автору.")


async def main():
    if not TOKEN:
        raise SystemExit("Не задан BOT_TOKEN (см. README.md)")
    logging.basicConfig(level=logging.INFO)
    bot = Bot(TOKEN)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
