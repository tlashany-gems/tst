"""
🎵 Telegram Music Bot - Fixed: downloads audio file before streaming
"""

import asyncio
import os
import re
import logging
import subprocess
import shutil
import tempfile
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
temp_files: dict[int, str] = {}


def get_queue(chat_id):
    queues.setdefault(chat_id, [])
    return queues[chat_id]


def download_audio(query):
    """
    الاصلاح الرئيسي: بنحمل الاغنية كـ mp3 مؤقت بدل ما نبعت URL مباشرة
    URL بتنتهي صلاحيتها بسرعة - الملف المحلي بيشتغل دايما
    """
    tmp_dir = tempfile.mkdtemp()
    out_template = os.path.join(tmp_dir, "audio.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        },
    }

    is_url = re.match(r"https?://", query)
    searches = [query] if is_url else [f"scsearch1:{query}", f"ytsearch1:{query}"]

    for search in searches:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(search, download=True)
                if not info:
                    continue
                if "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    if not entries:
                        continue
                    info = entries[0]

                audio_path = os.path.join(tmp_dir, "audio.mp3")
                if not os.path.exists(audio_path):
                    files = os.listdir(tmp_dir)
                    if files:
                        audio_path = os.path.join(tmp_dir, files[0])

                if not os.path.exists(audio_path):
                    logger.warning(f"File not found after download in: {tmp_dir}")
                    continue

                logger.info(f"Downloaded: {audio_path} ({os.path.getsize(audio_path)} bytes)")
                return {
                    "title": info.get("title", "Unknown"),
                    "file_path": audio_path,
                    "tmp_dir": tmp_dir,
                    "duration": info.get("duration", 0),
                    "webpage": info.get("webpage_url", ""),
                }
        except Exception as e:
            logger.warning(f"download failed '{search}': {e}")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    return None


def fmt_duration(seconds):
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def cleanup_temp(chat_id):
    tmp_dir = temp_files.pop(chat_id, None)
    if tmp_dir and os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)
        logger.info(f"Cleaned up temp for chat {chat_id}")


async def play_in_vc(chat_id, track):
    cleanup_temp(chat_id)
    playing[chat_id] = track
    temp_files[chat_id] = track["tmp_dir"]
    stream = MediaStream(track["file_path"], video_flags=MediaStream.Flags.IGNORE)
    await call_py.play(chat_id, stream)
    logger.info(f"Playing from file: {track['file_path']}")


async def play_next(chat_id):
    queue = get_queue(chat_id)
    if queue:
        await play_in_vc(chat_id, queue.pop(0))
    else:
        playing.pop(chat_id, None)
        cleanup_temp(chat_id)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass


@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    name = msg.from_user.first_name if msg.from_user else "صديقي"
    await msg.reply_text(
        f"اهلا {name}!\n\n"
        "بوت الموسيقى جاهز!\n\n"
        "/play <اسم> شغل في الدردشة الصوتية\n"
        "/skip تخطي\n"
        "/stop وقف\n"
        "/queue القائمة\n"
        "/now الشغال دلوقتي\n\n"
        "مثال: /play تامر عاشور"
    )


@bot.on_message(filters.command("play"))
async def cmd_play(_, msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("اكتب اسم الاغنية!")
        return
    query = " ".join(msg.command[1:])
    chat_id = msg.chat.id

    status = await msg.reply_text(f"بدور على: {query}...")

    try:
        track = await asyncio.get_running_loop().run_in_executor(None, download_audio, query)
    except Exception as e:
        logger.error(f"Download error: {e}")
        await status.edit_text("حصل error اثناء التحميل، جرب تاني!")
        return

    if not track:
        await status.edit_text("مش لاقيها، جرب اسم تاني!")
        return

    dur = fmt_duration(track["duration"])

    if playing.get(chat_id):
        get_queue(chat_id).append(track)
        pos = len(get_queue(chat_id))
        await status.edit_text(f"اتضافت للقائمة #{pos}:\n{track['title']}\n{dur}")
        return

    await status.edit_text(f"جاري التشغيل:\n{track['title']}\n{dur}")
    try:
        await play_in_vc(chat_id, track)
        await status.edit_text(f"شغال دلوقتي:\n{track['title']}\n{dur}")
    except Exception as e:
        logger.error(f"VC error: {e}")
        err_msg = str(e)
        hint = ""
        if "not participant" in err_msg.lower():
            hint = "\n\nالحل: اضف الحساب المساعد للجروب يدويا"
        elif "forbidden" in err_msg.lower():
            hint = "\n\nالحل: غير اعدادات الجروب وسمح للاعضاء بالبث في الـ VC"
        await status.edit_text(f"مش قادر يشغلها في الـ VC!\n{track['title']}\n\nError: {err_msg[:150]}{hint}")
        cleanup_temp(chat_id)


@bot.on_message(filters.command("stop"))
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)
    cleanup_temp(chat_id)
    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass
    await msg.reply_text("تم الايقاف!")


@bot.on_message(filters.command("skip"))
async def cmd_skip(_, msg: Message):
    if not playing.get(msg.chat.id):
        await msg.reply_text("مفيش اغنية!")
        return
    await msg.reply_text("تخطي...")
    await play_next(msg.chat.id)


@bot.on_message(filters.command("queue"))
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    current = playing.get(chat_id)
    queue = get_queue(chat_id)
    if not current and not queue:
        await msg.reply_text("القائمة فاضية!")
        return
    lines = ["قائمة الانتظار:\n"]
    if current:
        lines.append(f"شغال: {current['title']}")
    for i, t in enumerate(queue, 1):
        lines.append(f"{i}. {t['title']} - {fmt_duration(t['duration'])}")
    await msg.reply_text("\n".join(lines))


@bot.on_message(filters.command("now"))
async def cmd_now(_, msg: Message):
    track = playing.get(msg.chat.id)
    if not track:
        await msg.reply_text("مفيش اغنية شغالة.")
        return
    await msg.reply_text(
        f"شغال دلوقتي:\n{track['title']}\n"
        f"{fmt_duration(track['duration'])}\n{track['webpage']}"
    )


try:
    from pytgcalls import filters as tgf
    @call_py.on_update(tgf.stream_end)
    async def on_stream_end(_, update):
        await play_next(update.chat_id)
except Exception:
    pass


async def main():
    if not shutil.which("ffmpeg"):
        logger.info("Installing ffmpeg...")
        try:
            subprocess.run(["apt-get", "update", "-qq"], check=True, capture_output=True)
            subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], check=True, capture_output=True)
            logger.info("ffmpeg installed!")
        except Exception as e:
            logger.error(f"ffmpeg install failed: {e}")
    else:
        logger.info("ffmpeg already present")

    logger.info("Starting...")
    await bot.start()
    logger.info("Bot started")
    await userbot.start()
    logger.info("Userbot started")
    await call_py.start()
    logger.info("PyTgCalls started - ready!")
    await idle()


if __name__ == "__main__":
    asyncio.run(main())
