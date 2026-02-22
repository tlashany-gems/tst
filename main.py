"""
🎵 Telegram Voice Chat Music Bot
"""

import asyncio
import os
import re
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, idle
from pytgcalls.types import MediaStream
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
USER_SESSION = os.getenv("USER_SESSION", "")

logger.info(f"API_ID: {API_ID}")
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:15]}...")
logger.info(f"USER_SESSION length: {len(USER_SESSION)}")

bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION)
call_py = PyTgCalls(userbot)

queues:  dict[int, list] = {}
playing: dict[int, dict] = {}


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
        "skip_download": True,
    }
    if not re.match(r"https?://", query):
        query = f"ytsearch1:{query}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            stream_url = None
            for fmt in reversed(info.get("formats", [])):
                if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none":
                    stream_url = fmt["url"]
                    break
            if not stream_url:
                stream_url = info["url"]
            return {
                "title": info.get("title", "Unknown"),
                "url": stream_url,
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
    stream = MediaStream(track["url"])
    try:
        await call_py.change_stream(chat_id, stream)
    except Exception:
        await call_py.play(chat_id, stream)


async def play_next(chat_id):
    queue = get_queue(chat_id)
    if queue:
        await play_track(chat_id, queue.pop(0))
    else:
        playing.pop(chat_id, None)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass


@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    logger.info(f"/start من {msg.from_user.id}")
    name = msg.from_user.first_name if msg.from_user else "صديقي"
    await msg.reply_text(
        f"👋 أهلاً **{name}**!\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🎵 **بوت الموسيقى جاهز!**\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "▶️ `/play <اسم>` — شغّل\n"
        "🎵 `/now` — الشغال دلوقتي\n"
        "📋 `/queue` — القائمة\n"
        "⏭️ `/skip` — تخطي\n"
        "⏹️ `/stop` — وقف\n"
        "🔊 `/volume <1-200>` — الصوت\n\n"
        "💡 مثال: `/play Fairuz`"
    )


@bot.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    logger.info(f"/play من {msg.chat.id}")
    if len(msg.command) < 2:
        await msg.reply_text("❌ اكتب اسم الأغنية!\nمثال: `/play Fairuz`")
        return
    query = " ".join(msg.command[1:])
    chat_id = msg.chat.id
    status = await msg.reply_text(f"🔍 بدور على: **{query}**...")
    track = await asyncio.get_event_loop().run_in_executor(None, search_song, query)
    if not track:
        await status.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return
    dur = fmt_duration(track["duration"])
    if playing.get(chat_id):
        get_queue(chat_id).append(track)
        pos = len(get_queue(chat_id))
        await status.edit_text(f"✅ **اتضافت للقائمة #{pos}:**\n🎵 {track['title']}\n⏱️ {dur}")
    else:
        await status.edit_text(f"▶️ **بيشغل:**\n🎵 {track['title']}\n⏱️ {dur}")
        await play_track(chat_id, track)


@bot.on_message(filters.command("now"))
async def cmd_now(_, msg: Message):
    track = playing.get(msg.chat.id)
    if not track:
        await msg.reply_text("😶 مفيش أغنية شغالة.")
        return
    await msg.reply_text(
        f"▶️ **شغال دلوقتي:**\n🎵 [{track['title']}]({track['webpage']})\n⏱️ {fmt_duration(track['duration'])}",
        disable_web_page_preview=True,
    )


@bot.on_message(filters.command("skip"))
async def cmd_skip(_, msg: Message):
    if not playing.get(msg.chat.id):
        await msg.reply_text("❌ مفيش أغنية!")
        return
    await msg.reply_text("⏭️ تخطي...")
    await play_next(msg.chat.id)


@bot.on_message(filters.command("stop"))
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)
    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass
    await msg.reply_text("⏹️ تم الإيقاف!")


@bot.on_message(filters.command("queue"))
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    queue = get_queue(chat_id)
    current = playing.get(chat_id)
    if not current and not queue:
        await msg.reply_text("📋 القائمة فاضية!")
        return
    lines = ["📋 **قائمة الانتظار:**\n"]
    if current:
        lines.append(f"▶️ **{current['title']}** ← شغال\n")
    for i, t in enumerate(queue, 1):
        lines.append(f"`{i}.` {t['title']} — ⏱️ {fmt_duration(t['duration'])}")
    if not queue:
        lines.append("_مفيش أغاني جاية_")
    await msg.reply_text("\n".join(lines))


@bot.on_message(filters.command("volume"))
async def cmd_volume(_, msg: Message):
    if len(msg.command) < 2 or not msg.command[1].isdigit():
        await msg.reply_text("❌ مثال: `/volume 80`")
        return
    vol = max(1, min(200, int(msg.command[1])))
    try:
        await call_py.change_volume_call(msg.chat.id, vol)
        await msg.reply_text(f"🔊 الصوت: **{vol}%**")
    except Exception:
        await msg.reply_text("❌ مش قادر أغير الصوت.")


try:
    from pytgcalls import filters as tgf
    @call_py.on_update(tgf.stream_end)
    async def on_end(_, update):
        await play_next(update.chat_id)
    logger.info("✅ stream_end v2.x")
except Exception:
    @call_py.on_stream_end()
    async def on_end(_, update):
        await play_next(update.chat_id)
    logger.info("✅ stream_end legacy")


async def main():
    logger.info("🚀 بيشتغل...")
    await bot.start()
    logger.info("✅ Bot started")
    await userbot.start()
    logger.info("✅ Userbot started")
    await call_py.start()
    logger.info("✅ PyTgCalls started — البوت جاهز!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
