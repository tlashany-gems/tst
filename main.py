"""
🎵 Telegram Music Bot - Bot API + PyTgCalls
"""

import asyncio
import os
import re
import logging
from dotenv import load_dotenv

from pyrogram import Client, idle
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
USER_SESSION = os.getenv("USER_SESSION", "")

userbot = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=USER_SESSION)
call_py = PyTgCalls(userbot)

queues:  dict[int, list] = {}
playing: dict[int, dict] = {}


def get_queue(chat_id):
    queues.setdefault(chat_id, [])
    return queues[chat_id]


def search_song(query):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "socket_timeout": 15,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        },
    }
    is_url = re.match(r"https?://", query)
    searches = [query] if is_url else [f"scsearch1:{query}", f"ytsearch1:{query}"]
    for search in searches:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search, download=False)
                if not info:
                    continue
                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        continue
                    info = entries[0]
                stream_url = None
                for fmt in reversed(info.get("formats", [])):
                    if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none":
                        stream_url = fmt.get("url")
                        break
                if not stream_url:
                    stream_url = info.get("url")
                if not stream_url:
                    continue
                return {
                    "title": info.get("title", "Unknown"),
                    "url": stream_url,
                    "duration": info.get("duration", 0),
                    "webpage": info.get("webpage_url", ""),
                }
        except Exception as e:
            logger.warning(f"search failed '{search}': {e}")
    return None


def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


async def play_in_vc(chat_id, track):
    playing[chat_id] = track
    stream = MediaStream(
        track["url"],
        audio_flags=MediaStream.Flags.IGNORE_PENDING,
    )
    try:
        await call_py.play(chat_id, stream)
        logger.info(f"play() ok: {track['title']}")
    except Exception as e:
        logger.error(f"play() failed: {e}")
        raise


async def play_next(chat_id):
    queue = get_queue(chat_id)
    if queue:
        await play_in_vc(chat_id, queue.pop(0))
    else:
        playing.pop(chat_id, None)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass


# ===== HANDLERS =====

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "صديقي"
    await update.message.reply_text(
        f"👋 أهلاً {name}!\n\n"
        "🎵 بوت الموسيقى جاهز!\n\n"
        "▶️ /play <اسم> — شغّل في الدردشة الصوتية\n"
        "⏭️ /skip — تخطي\n"
        "⏹️ /stop — وقف\n"
        "📋 /queue — القائمة\n"
        "🎵 /now — الشغال دلوقتي\n\n"
        "💡 مثال: /play تامر عاشور"
    )


async def play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ اكتب اسم الأغنية!")
        return
    query = " ".join(ctx.args)
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(f"🔍 بدور على: {query}...")
    try:
        track = await asyncio.get_running_loop().run_in_executor(None, search_song, query)
    except Exception as e:
        await msg.edit_text("❌ حصل error، جرب تاني!")
        return
    if not track:
        await msg.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return
    dur = fmt_duration(track["duration"])
    if playing.get(chat_id):
        get_queue(chat_id).append(track)
        pos = len(get_queue(chat_id))
        await msg.edit_text(f"✅ اتضافت للقائمة #{pos}:\n🎵 {track['title']}\n⏱️ {dur}")
        return
    await msg.edit_text(f"▶️ بيشغل:\n🎵 {track['title']}\n⏱️ {dur}")
    try:
        await play_in_vc(chat_id, track)
    except Exception as e:
        logger.error(f"VC error: {e}")
        await msg.edit_text(
            f"⚠️ لاقيت الأغنية بس مش قادر يشغلها في الـ Voice Chat!\n"
            f"🎵 {track['title']}\n🔗 {track['webpage']}\n\n"
            "تأكد إن الـ Voice Chat شغال والحساب المساعد Admin."
        )


async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)
    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass
    await update.message.reply_text("⏹️ تم الإيقاف!")


async def skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not playing.get(chat_id):
        await update.message.reply_text("❌ مفيش أغنية!")
        return
    await update.message.reply_text("⏭️ تخطي...")
    await play_next(chat_id)


async def queue_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    current = playing.get(chat_id)
    queue = get_queue(chat_id)
    if not current and not queue:
        await update.message.reply_text("📋 القائمة فاضية!")
        return
    lines = ["📋 قائمة الانتظار:\n"]
    if current:
        lines.append(f"▶️ {current['title']} ← شغال")
    for i, t in enumerate(queue, 1):
        lines.append(f"{i}. {t['title']} — {fmt_duration(t['duration'])}")
    await update.message.reply_text("\n".join(lines))


async def now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    track = playing.get(update.effective_chat.id)
    if not track:
        await update.message.reply_text("😶 مفيش أغنية شغالة.")
        return
    await update.message.reply_text(
        f"▶️ شغال دلوقتي:\n🎵 {track['title']}\n"
        f"⏱️ {fmt_duration(track['duration'])}\n🔗 {track['webpage']}"
    )


# ===== STREAM END =====
try:
    from pytgcalls import filters as tgf
    @call_py.on_update(tgf.stream_end)
    async def on_stream_end(_, update):
        await play_next(update.chat_id)
except Exception:
    pass


# ===== MAIN =====
async def main():
    logger.info("🚀 Starting...")

    # ابدأ userbot
    await userbot.start()
    logger.info("✅ Userbot started")
    await call_py.start()
    logger.info("✅ PyTgCalls started")

    # ابدأ البوت في نفس الـ event loop
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("now", now))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    logger.info("✅ Bot polling started! البوت جاهز 🎵")

    # استنى للأبد
    await idle()

    # cleanup
    await app.updater.stop()
    await app.stop()
    await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
