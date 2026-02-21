"""
🎵 Telegram Voice Chat Music Bot
py-tgcalls + pyrofork (متوافقين 100%)
"""

import asyncio
import os
import re
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls, idle
from pytgcalls import filters as fl
from pytgcalls.types import MediaStream, Update
from pytgcalls.types.stream import StreamAudioEnded, StreamVideoEnded
import yt_dlp

load_dotenv()

# ─── إعدادات (من Railway Variables) ───
API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
USER_SESSION = os.getenv("USER_SESSION", "")

# ─── Clients ───
bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

userbot = Client(
    "userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=USER_SESSION,
)

call_py = PyTgCalls(userbot)

# ─── State ───
queues:  dict[int, list] = {}
playing: dict[int, dict] = {}


# ─── Helpers ───
def get_queue(chat_id: int) -> list:
    if chat_id not in queues:
        queues[chat_id] = []
    return queues[chat_id]


def search_song(query: str) -> dict | None:
    ydl_opts = {
        "format"       : "bestaudio/best",
        "quiet"        : True,
        "no_warnings"  : True,
        "noplaylist"   : True,
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
                "title"   : info.get("title", "Unknown"),
                "url"     : stream_url,
                "duration": info.get("duration", 0),
                "webpage" : info.get("webpage_url", ""),
            }
    except Exception as e:
        print(f"[search error] {e}")
        return None


def fmt_duration(seconds) -> str:
    if not seconds:
        return "?"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


# ─── تشغيل ───
async def play_track(chat_id: int, track: dict):
    playing[chat_id] = track
    stream = MediaStream(track["url"])
    try:
        await call_py.change_stream(chat_id, stream)
    except Exception:
        await call_py.play(chat_id, stream)


async def play_next(chat_id: int):
    queue = get_queue(chat_id)
    if queue:
        await play_track(chat_id, queue.pop(0))
    else:
        playing.pop(chat_id, None)
        try:
            await call_py.leave_call(chat_id)
        except Exception:
            pass


# ─── أوامر ───
@bot.on_message(filters.command("start"))
async def cmd_start(_, msg: Message):
    await msg.reply_text(
        "🎵 **Music Bot**\n\n"
        "▶️ `/play <اسم الأغنية>` — شغّل\n"
        "🎵 `/now` — الأغنية الحالية\n"
        "⏭️ `/skip` — تخطي\n"
        "⏹️ `/stop` — وقف\n"
        "📋 `/queue` — القائمة\n"
        "🔊 `/volume <1-200>` — الصوت"
    )


@bot.on_message(filters.command("play") & filters.group)
async def cmd_play(_, msg: Message):
    if len(msg.command) < 2:
        await msg.reply_text("❌ اكتب اسم الأغنية!\nمثال: `/play Fairuz`")
        return
    query   = " ".join(msg.command[1:])
    chat_id = msg.chat.id
    status  = await msg.reply_text(f"🔍 بدور على: **{query}**...")
    track   = await asyncio.get_event_loop().run_in_executor(None, search_song, query)
    if not track:
        await status.edit_text("❌ مش لاقي الأغنية دي، جرب اسم تاني!")
        return
    dur = fmt_duration(track["duration"])
    if playing.get(chat_id):
        get_queue(chat_id).append(track)
        pos = len(get_queue(chat_id))
        await status.edit_text(
            f"✅ **اتضافت للقائمة:**\n🎵 {track['title']}\n⏱️ {dur}  |  📋 #{pos}"
        )
    else:
        await status.edit_text(f"▶️ **بيشغل:**\n🎵 {track['title']}\n⏱️ {dur}")
        await play_track(chat_id, track)


@bot.on_message(filters.command("now") & filters.group)
async def cmd_now(_, msg: Message):
    track = playing.get(msg.chat.id)
    if not track:
        await msg.reply_text("😶 مفيش أغنية شغالة دلوقتي.")
        return
    await msg.reply_text(
        f"▶️ **شغال دلوقتي:**\n"
        f"🎵 [{track['title']}]({track['webpage']})\n"
        f"⏱️ {fmt_duration(track['duration'])}",
        disable_web_page_preview=True,
    )


@bot.on_message(filters.command("skip") & filters.group)
async def cmd_skip(_, msg: Message):
    if not playing.get(msg.chat.id):
        await msg.reply_text("❌ مفيش أغنية شغالة!")
        return
    await msg.reply_text("⏭️ بيتخطى...")
    await play_next(msg.chat.id)


@bot.on_message(filters.command("stop") & filters.group)
async def cmd_stop(_, msg: Message):
    chat_id = msg.chat.id
    queues.pop(chat_id, None)
    playing.pop(chat_id, None)
    try:
        await call_py.leave_call(chat_id)
    except Exception:
        pass
    await msg.reply_text("⏹️ تم الإيقاف!")


@bot.on_message(filters.command("queue") & filters.group)
async def cmd_queue(_, msg: Message):
    chat_id = msg.chat.id
    queue   = get_queue(chat_id)
    current = playing.get(chat_id)
    if not current and not queue:
        await msg.reply_text("📋 القائمة فاضية!")
        return
    lines = ["📋 **قائمة الانتظار:**\n"]
    if current:
        lines.append(f"▶️ **{current['title']}** ← شغال دلوقتي\n")
    for i, t in enumerate(queue, 1):
        lines.append(f"`{i}.` {t['title']} — ⏱️ {fmt_duration(t['duration'])}")
    if not queue:
        lines.append("_مفيش أغاني جاية_")
    await msg.reply_text("\n".join(lines))


@bot.on_message(filters.command("volume") & filters.group)
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


# ─── Stream End (py-tgcalls v2.x API) ───
@call_py.on_update(fl.stream_end)
async def on_stream_end(_, update: Update):
    if isinstance(update, (StreamAudioEnded, StreamVideoEnded)):
        await play_next(update.chat_id)


# ─── تشغيل ───
async def main():
    print("🚀 بيشتغل...")
    await bot.start()
    await userbot.start()
    await call_py.start()
    print("✅ البوت جاهز!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())