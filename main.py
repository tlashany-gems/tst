"""
🎵 Telegram Music Bot
"""

import asyncio
import os
import re
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

queues:  dict[int, list] = {}
playing: dict[int, dict] = {}


def search_song(query):
    ydl_opts = {
        "format": "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "cookiefile": None,
        "extractor_args": {"youtube": {"skip": ["dash", "hls"]}},
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        },
    }
    # لو مش رابط، ابحث على YouTube
    if not re.match(r"https?://", query):
        query = f"ytsearch:{query}"
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                # خد أول نتيجة
                entries = [e for e in info["entries"] if e]
                if not entries:
                    return None
                info = entries[0]
            # جيب أفضل audio URL
            stream_url = None
            for fmt in reversed(info.get("formats", [])):
                if fmt.get("acodec") != "none" and fmt.get("vcodec") == "none":
                    stream_url = fmt.get("url")
                    break
            if not stream_url:
                stream_url = info.get("url")
            if not stream_url:
                return None
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


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "صديقي"
    await update.message.reply_text(
        f"👋 أهلاً {name}!\n\n"
        "🎵 بوت الموسيقى جاهز!\n\n"
        "▶️ /play <اسم أو رابط> — شغّل\n"
        "⏹️ /stop — وقف\n"
        "📋 /queue — القائمة\n"
        "⏭️ /skip — تخطي\n\n"
        "💡 مثال: /play Fairuz"
    )


async def play(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("❌ اكتب اسم الأغنية!\nمثال: /play Fairuz")
        return
    query = " ".join(ctx.args)
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(f"🔍 بدور على: {query}...")

    try:
        track = await asyncio.get_running_loop().run_in_executor(None, search_song, query)
    except Exception as e:
        logger.error(f"play error: {e}")
        await msg.edit_text("❌ حصل error، جرب تاني!")
        return

    if not track:
        await msg.edit_text("❌ مش لاقيها، جرب اسم أو رابط YouTube مباشر!")
        return

    dur = fmt_duration(track["duration"])
    if playing.get(chat_id):
        queues.setdefault(chat_id, []).append(track)
        pos = len(queues[chat_id])
        await msg.edit_text(f"✅ اتضافت للقائمة #{pos}:\n🎵 {track['title']}\n⏱️ {dur}")
    else:
        playing[chat_id] = track
        await msg.edit_text(
            f"▶️ بيشغل:\n🎵 {track['title']}\n⏱️ {dur}\n\n"
            f"🔗 [استمع هنا]({track['webpage']})",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        logger.info(f"Now playing: {track['title']}")


async def stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    playing.pop(chat_id, None)
    queues.pop(chat_id, None)
    await update.message.reply_text("⏹️ تم الإيقاف!")


async def skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not playing.get(chat_id):
        await update.message.reply_text("❌ مفيش أغنية!")
        return
    queue = queues.get(chat_id, [])
    if queue:
        next_track = queue.pop(0)
        playing[chat_id] = next_track
        dur = fmt_duration(next_track["duration"])
        await update.message.reply_text(f"⏭️ تخطي\n▶️ {next_track['title']}\n⏱️ {dur}")
    else:
        playing.pop(chat_id, None)
        await update.message.reply_text("⏭️ خلصت القائمة!")


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


async def now(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    track = playing.get(update.effective_chat.id)
    if not track:
        await update.message.reply_text("😶 مفيش أغنية شغالة.")
        return
    await update.message.reply_text(
        f"▶️ شغال دلوقتي:\n🎵 {track['title']}\n⏱️ {fmt_duration(track['duration'])}\n🔗 {track['webpage']}"
    )


def main():
    logger.info(f"🚀 Starting with token: {BOT_TOKEN[:10]}...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("skip", skip))
    app.add_handler(CommandHandler("queue", queue_cmd))
    app.add_handler(CommandHandler("now", now))
    logger.info("✅ Bot polling started!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
