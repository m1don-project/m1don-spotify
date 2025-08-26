import re
import os
import sys
import glob
import time
import subprocess
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ==== Читаем токены из переменных окружения ====
TOKEN = os.environ.get("TOKEN")
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

if not TOKEN or not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
    raise RuntimeError("Не заданы переменные окружения: TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET")

# ==== Папка для загрузок ====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ==== Telegram и Spotify ====
app = Application.builder().token(TOKEN).build()
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

# ==== Функция скачивания ====
def run_spotdl(url: str) -> str:
    """Скачать трек через spotdl и вернуть путь к mp3."""
    # Чистим старые mp3
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "**", "*.mp3"), recursive=True):
        try:
            os.remove(f)
        except:
            pass

    # Команда для spotDL (с lyrics=genius чтобы не падало на azlyrics)
    cmd = [
        sys.executable, "-m", "spotdl", "download", url,
        "--format", "mp3",
        "--bitrate", "192k",
        "--output", DOWNLOAD_DIR,
        "--lyrics", "genius"
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise Exception(
            "spotdl завершился с ошибкой "
            f"(код {proc.returncode}).\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}"
        )

    time.sleep(0.2)  # пауза чтобы файл дописался

    # Ищем скачанный mp3
    files = glob.glob(os.path.join(DOWNLOAD_DIR, "**", "*.mp3"), recursive=True)
    if not files:
        raise Exception("Файл .mp3 не найден после загрузки.\n\nSTDOUT:\n" + proc.stdout + "\n" + proc.stderr)

    newest = max(files, key=os.path.getmtime)
    return newest

# ==== Обработчик сообщений ====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    if re.search(r'(https?://)?(www\.)?open\.spotify\.com/', text):
        await update.message.reply_text("Скачиваю трек...")
        try:
            mp3_path = run_spotdl(text)
            with open(mp3_path, "rb") as f:
                await update.message.reply_audio(f, caption=os.path.basename(mp3_path))
        except Exception as e:
            err = str(e)
            if len(err) > 3500:
                err = err[:3500] + "\n... (обрезано)"
            await update.message.reply_text("Ошибка при скачивании:\n" + err)
        finally:
            # Чистим папку
            for f in glob.glob(os.path.join(DOWNLOAD_DIR, "**", "*.mp3"), recursive=True):
                try:
                    os.remove(f)
                except:
                    pass
    else:
        await update.message.reply_text("Отправьте ссылку на трек Spotify.")

# ==== Запуск бота ====
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    app.run_polling()
