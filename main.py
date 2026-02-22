"""
🎵 Telegram Voice Chat Music Bot
"""

import asyncio
import os
import re
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pytgcalls import GroupCallFile
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
USER_SESSION = os.getenv("USER_SESSION", "")

bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION)

queues:  dict[int, list] = {}
playing: dict[int, dict] = {}
calls:   dict[int, GroupCallFile] = {}


def get_queue(chat_id):
    if chat_id not in queues:
        queues[chat_id] = []
    return queues[chat_id]


def search_song(query):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": f"/tmp/%(id)s.%(ext)s",
    }
    if not re.match(r"https?://", query):
        query = f"ytsearch1:{query}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if "entries" in info:
                info = info["entries"][0]
            filename = ydl.prepare_filename(info)
            return {
                "title": info.get("title", "Unknown"),
                "file": filename,
                "duration": info.get("duration", 0),
                "webpage": info.get("webpage_url", ""),
            }
    except Exception as e:
        logger.error(f"search error: {e}")
        return None


def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


async def play_track(chat_id, track):
    playing[chat_id] = track
    if chat_id not in calls:
        call = GroupCallFile(userbot)
        calls[chat_id] = call
        await call.start(chat_id, track["file"])
    else:
        calls[chat_id].input_filename = track["file"]


@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    logger.info(f"/start from {msg.from_user.id}")
    name = msg.from_user.first_name if msg.from_user else "صديقي"
    await msg.reply_text(
        f"👋 أهلاً **{name}**!\n"
        "🎵 **بوت الموسيقى جاهز!**\n\n"
        "▶️ `/play <اسم>` — شغّل\n"
        "⏹️ `/stop` — وقف\n"
        "💡 مثال: `/play Fairuz`"
    )


@bot.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    logger.info(f"/play from {msg.chat.id}")
    if len(msg.command) < 2:
        await msg.reply_text("❌ اكتب اسم الأغنية!")
        return
    query = " ".join(msg.command[1:])
    chat_id = msg.chat.id
    status = await msg.reply_text(f"🔍 بدور على: **{query}**...")
    track = await asyncio.get_running_loop().run_in_executor(None, search_song, query)
    if not track:
        await status.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return
    dur = fmt_duration(track["duration"])
    await status.edit_text(f"▶️ **بيشغل:**\n🎵 {track['title']}\n⏱️ {dur}")
    await play_track(chat_id, track)


@bot.on_message(filters.command("stop"))
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)
    if chat_id in calls:
        await calls[chat_id].stop()
        calls.pop(chat_id)
    await msg.reply_text("⏹️ تم الإيقاف!")


async def main():
    logger.info("🚀 Starting...")
    await bot.start()
    logger.info("✅ Bot started")
    await userbot.start()
    logger.info("✅ Userbot started — البوت جاهز!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
