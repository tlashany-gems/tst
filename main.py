"""
🎵 Telegram Music Bot - All in one loop with pyrofork
"""

import asyncio
import os
import re
import logging
import subprocess
import shutil
from dotenv import load_dotenv
from pyrogram import Client, filters, idle
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import yt_dlp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
USER_SESSION = os.getenv("USER_SESSION", "")

bot     = Client("bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
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


async def ensure_userbot_in_chat(chat_id):
    """
    ✅ الإصلاح الرئيسي: يضمن إن الـ userbot موجود في الجروب قبل ما يبدأ يبث
    الـ userbot مش محتاج يكون Admin — بس لازم يكون عضو في الجروب
    """
    try:
        await userbot.get_chat_member(chat_id, "me")
        logger.info(f"✅ Userbot already in chat {chat_id}")
    except Exception:
        try:
            # لو مش موجود، يطلب من البوت يضيفه
            invite = await bot.export_chat_invite_link(chat_id)
            await userbot.join_chat(invite)
            logger.info(f"✅ Userbot joined chat {chat_id} via invite link")
        except Exception as e:
            logger.warning(f"⚠️ Could not auto-join userbot: {e}")
            # مش هيوقف البوت، هيحاول يكمل


async def play_in_vc(chat_id, track):
    playing[chat_id] = track
    # ✅ تأكد إن الـ userbot في الجروب أولاً
    await ensure_userbot_in_chat(chat_id)
    stream = MediaStream(track["url"], video_flags=MediaStream.Flags.IGNORE)
    await call_py.play(chat_id, stream)
    logger.info(f"✅ playing in VC: {track['title']}")


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

@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    name = msg.from_user.first_name if msg.from_user else "صديقي"
    await msg.reply_text(
        f"👋 أهلاً {name}!\n\n"
        "🎵 بوت الموسيقى جاهز!\n\n"
        "▶️ /play <اسم> — شغّل في الدردشة الصوتية\n"
        "⏭️ /skip — تخطي\n"
        "⏹️ /stop — وقف\n"
        "📋 /queue — القائمة\n"
        "🎵 /now — الشغال دلوقتي\n\n"
        "💡 مثال: /play تامر عاشور"
    )


@bot.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("❌ اكتب اسم الأغنية!")
        return
    query = " ".join(msg.command[1:])
    chat_id = msg.chat.id
    status = await msg.reply_text(f"🔍 بدور على: {query}...")
    try:
        track = await asyncio.get_running_loop().run_in_executor(None, search_song, query)
    except Exception as e:
        logger.error(f"Search error: {e}")
        await status.edit_text("❌ حصل error، جرب تاني!")
        return
    if not track:
        await status.edit_text("❌ مش لاقيها، جرب اسم تاني!")
        return
    dur = fmt_duration(track["duration"])
    if playing.get(chat_id):
        get_queue(chat_id).append(track)
        pos = len(get_queue(chat_id))
        await status.edit_text(f"✅ اتضافت للقائمة #{pos}:\n🎵 {track['title']}\n⏱️ {dur}")
        return
    await status.edit_text(f"▶️ بيشغل:\n🎵 {track['title']}\n⏱️ {dur}")
    try:
        await play_in_vc(chat_id, track)
    except Exception as e:
        logger.error(f"VC error: {e}")
        # ✅ رسالة خطأ أوضح مع سبب المشكلة
        err_msg = str(e)
        hint = ""
        if "not participant" in err_msg.lower() or "user not participant" in err_msg.lower():
            hint = "\n\n💡 الحل: أضف الحساب المساعد للجروب يدوياً أو تأكد إنه عضو"
        elif "forbidden" in err_msg.lower():
            hint = "\n\n💡 الحل: غيّر إعدادات الجروب وسمح لكل الأعضاء بالبث في الـ VC"
        await status.edit_text(
            f"⚠️ لاقيت الأغنية بس مش قادر يشغلها!\n"
            f"🎵 {track['title']}\n🔗 {track['webpage']}\n\n"
            f"Error: {err_msg[:150]}{hint}"
        )


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


@bot.on_message(filters.command("skip"))
async def cmd_skip(_, msg: Message):
    if not playing.get(msg.chat.id):
        await msg.reply_text("❌ مفيش أغنية!")
        return
    await msg.reply_text("⏭️ تخطي...")
    await play_next(msg.chat.id)


@bot.on_message(filters.command("queue"))
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    current = playing.get(chat_id)
    queue = get_queue(chat_id)
    if not current and not queue:
        await msg.reply_text("📋 القائمة فاضية!")
        return
    lines = ["📋 قائمة الانتظار:\n"]
    if current:
        lines.append(f"▶️ {current['title']} ← شغال")
    for i, t in enumerate(queue, 1):
        lines.append(f"{i}. {t['title']} — {fmt_duration(t['duration'])}")
    await msg.reply_text("\n".join(lines))


@bot.on_message(filters.command("now"))
async def cmd_now(_, msg: Message):
    track = playing.get(msg.chat.id)
    if not track:
        await msg.reply_text("😶 مفيش أغنية شغالة.")
        return
    await msg.reply_text(
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
    # تثبيت ffmpeg
    if not shutil.which("ffmpeg"):
        logger.info("📦 Installing ffmpeg...")
        try:
            subprocess.run(["apt-get", "update", "-qq"], check=True, capture_output=True)
            subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], check=True, capture_output=True)
            logger.info("✅ ffmpeg installed!")
        except Exception as e:
            logger.error(f"ffmpeg install failed: {e}")
    else:
        logger.info("✅ ffmpeg already present")

    logger.info("🚀 Starting...")
    await bot.start()
    logger.info("✅ Bot started")
    await userbot.start()
    logger.info("✅ Userbot started")
    await call_py.start()
    logger.info("✅ PyTgCalls started — جاهز!")
    await idle()


if __name__ == "__main__":
    asyncio.run(main())
