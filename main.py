import os
import logging
import io
import datetime
import speech_recognition as sr
from pydub import AudioSegment
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
from docx import Document
import PyPDF2
from deep_translator import GoogleTranslator
from langdetect import detect
from gtts import gTTS
from dotenv import load_dotenv

load_dotenv()

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIRMA = "By🦅𝓣𝓽ͭ𝓱ͪ𝓮ͤ𝓖𝓲𝓽ͭ𝓪ͣ𝓷𝓸 🦅"
HIST_DIR = "conversaciones"

os.makedirs(HIST_DIR, exist_ok=True)

AVAILABLE_ACCENTS = {
    'es': 'Español',
    'en': 'English'
}

SPEED_OPTIONS = {
    'lento': {'speed': True, 'name': 'Lento'},
    'normal': {'speed': False, 'name': 'Normal'}
}

user_preferences = {}

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= UTILIDADES =================
def save_history(uid, role, text):
    file_path = os.path.join(HIST_DIR, f"user_{uid}.txt")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {role}: {text}\n")

def detect_language(text):
    try:
        return detect(text)
    except:
        return 'unknown'

def translate_text(text, target):
    try:
        return GoogleTranslator(source='auto', target=target).translate(text)
    except:
        return text

def tts(text, lang, slow=False):
    tts = gTTS(text=text, lang=lang, slow=slow)
    audio = io.BytesIO()
    tts.write_to_fp(audio)
    audio.seek(0)
    return audio

def speech_to_text(audio_bytes):
    recognizer = sr.Recognizer()
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    wav = io.BytesIO()
    audio.export(wav, format="wav")
    wav.seek(0)

    with sr.AudioFile(wav) as source:
        audio_data = recognizer.record(source)
        return recognizer.recognize_google(audio_data)

# ================= START =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎧 Conversación bilingüe", callback_data="bilingual")],
        [InlineKeyboardButton("📄 Exportar conversaciones", callback_data="export")]
    ]

    await update.message.reply_text(
        "🤖 BOT INTÉRPRETE EMPRESARIAL\n\n"
        "Texto, documentos, audios\n"
        "Traducción automática\n"
        "Subtítulos\n"
        "Historial\n"
        "Conversación bilingüe\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= BOTONES =================
async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})

    if q.data == "bilingual":
        user_preferences[uid]['bilingual'] = not user_preferences[uid].get('bilingual', False)
        estado = "ACTIVADO" if user_preferences[uid]['bilingual'] else "DESACTIVADO"
        await q.edit_message_text(f"🎧 Modo intérprete: {estado}")

    elif q.data == "export":
        file_path = os.path.join(HIST_DIR, f"user_{uid}.txt")
        if not os.path.exists(file_path):
            await q.edit_message_text("No hay conversaciones registradas.")
            return
        await context.bot.send_document(chat_id=uid, document=open(file_path, "rb"))

# ================= AUDIO =================
async def handle_voice(update, context):
    uid = update.effective_user.id

    if not user_preferences.get(uid, {}).get("bilingual"):
        return

    voice = await context.bot.get_file(update.message.voice.file_id)
    audio_bytes = await voice.download_as_bytearray()

    try:
        original_text = speech_to_text(audio_bytes)
    except:
        await update.message.reply_text("No pude reconocer el audio.")
        return

    lang = detect_language(original_text)

    if lang == "es":
        translated = translate_text(original_text, "en")
        audio = tts(translated, "en")
    else:
        translated = translate_text(original_text, "es")
        audio = tts(translated, "es")

    save_history(uid, "Usuario", original_text)
    save_history(uid, "Bot", translated)

    await update.message.reply_text(f"📝 Subtítulos:\n{original_text}\n\n🌍 Traducción:\n{translated}")
    await update.message.reply_voice(audio)

# ================= MAIN =================
def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()

if __name__ == "__main__":
    main()
