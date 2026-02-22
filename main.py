"""
🎵 Telegram Music Bot
- python-telegram-bot: للأوامر
- pyrofork + py-tgcalls: للصوت في Voice Chat
"""

import asyncio
import os
import re
import logging
import threading
from dotenv import load_dotenv

# Telegram Bot
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Voice Chat
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
USER_SESSION = os.getenv("USER_SESSION", "")

# Userbot للصوت
userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION)
call_py = PyTgCalls(userbot)

queues:  dict[int, list] = {}
playing: dict[int, dict] = {}

# نحتاج event loop مشترك
loop = asyncio.new_event_loop()


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
        logger.info(f"✅ change_stream: {track['title']}")
    except Exception:
        await call_py.play(chat_id, stream)
        logger.info(f"✅ play: {track['title']}")


async def play_next(chat_id):
    queue = queues.get(chat_id, [])
    if queue:
        await play_track(chat_id, queue.pop(0))
    else:
        playing.pop(chat_id, None)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass


# ===== BOT COMMANDS =====

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "صديقي"
    await update.message.reply_text(
        f"👋 أهلاً {name}!\n\n"
        "🎵 بوت الموسيقى جاهز!\n\n"
        "▶️ /play <اسم> — شغّل في Voice Chat\n"
        "⏹️ /stop — وقف\n"
        "📋 /queue — القائمة\n"
        "⏭️ /skip — تخطي\n"
        "🔊 /volume <1-200> — الصوت\n\n"
        "💡 مثال: /play Fairuz"
    )


async def play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ اكتب اسم الأغنية!\nمثال: /play Fairuz")
        return
    query = " ".join(ctx.args)
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(f"🔍 بدور على: {query}...")

    track = await asyncio.get_running_loop().run_in_executor(None, search_song, query)
    if not track:
        await msg.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return

    dur = fmt_duration(track["duration"])

    if playing.get(chat_id):
        queues.setdefault(chat_id, []).append(track)
        pos = len(queues[chat_id])
        await msg.edit_text(f"✅ اتضافت للقائمة #{pos}:\n🎵 {track['title']}\n⏱️ {dur}")
    else:
        await msg.edit_text(f"▶️ بيشغل:\n🎵 {track['title']}\n⏱️ {dur}")
        asyncio.run_coroutine_threadsafe(play_track(chat_id, track), loop)


async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    playing.pop(chat_id, None)
    queues.pop(chat_id, None)
    asyncio.run_coroutine_threadsafe(call_py.leave_call(chat_id), loop)
    await update.message.reply_text("⏹️ تم الإيقاف!")


async def skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not playing.get(chat_id):
        await update.message.reply_text("❌ مفيش أغنية!")
        return
    asyncio.run_coroutine_threadsafe(play_next(chat_id), loop)
    await update.message.reply_text("⏭️ تخطي...")


async def volume(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("❌ مثال: /volume 80")
        return
    vol = max(1, min(200, int(ctx.args[0])))
    chat_id = update.effective_chat.id
    asyncio.run_coroutine_threadsafe(call_py.change_volume_call(chat_id, vol), loop)
    await update.message.reply_text(f"🔊 الصوت: {vol}%")


async def queue_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current = playing.get(chat_id)
    queue = queues.get(chat_id, [])
    if not current and not queue:
        await update.message.reply_text("📋 القائمة فاضية!")
        return
    lines = ["📋 قائمة الانتظار:\n"]
    if current:
        lines.append(f"▶️ {current['title']} ← شغال")
    for i, t in enumerate(queue, 1):
        lines.append(f"{i}. {t['title']} — {fmt_duration(t['duration'])}")
    await update.message.reply_text("\n".join(lines))


# ===== VOICE CHAT LOOP =====

def run_voice_loop():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_voice())
    loop.run_forever()


async def start_voice():
    await userbot.start()
    logger.info("✅ Userbot started")
    await call_py.start()
    logger.info("✅ PyTgCalls started")

    try:
        from pytgcalls import filters as tgf
        @call_py.on_update(tgf.stream_end)
        async def on_end(_, update):
            await play_next(update.chat_id)
        logger.info("✅ stream_end registered")
    except Exception as e:
        logger.warning(f"stream_end: {e}")


# ===== MAIN =====

def main():
    logger.info("🚀 Starting...")

    # شغل الـ voice loop في thread منفصل
    t = threading.Thread(target=run_voice_loop, daemon=True)
    t.start()
    logger.info("✅ Voice thread started")

    # شغل الـ bot
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("volume", volume))
    app.add_handler(CommandHandler("queue", queue_cmd))

    logger.info("✅ Bot polling started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
