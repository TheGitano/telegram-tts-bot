import os
import logging
import io
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

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIRMA = "By🦅𝓣𝓽ͭ𝓱ͪ𝓮ͤ𝓖𝓲𝓽ͭ𝓪ͣ𝓷𝓸 🦅"

AVAILABLE_ACCENTS = {
    'es': '🇪🇸 Español',
    'en': '🇺🇸 English'
}

SPEED_OPTIONS = {
    'lento': {'speed': True, 'name': '🐌 Lento'},
    'normal': {'speed': False, 'name': '✅ Normal'}
}

user_preferences = {}

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= UTILIDADES =================
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
    tts = gTTS(text=f"{text}\n\n{FIRMA}", lang=lang, slow=slow)
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

# ================= COMANDOS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🎧 Conversación bilingüe", callback_data="bilingual")],
        [InlineKeyboardButton("🗣 Acento", callback_data="accent_menu")],
        [InlineKeyboardButton("⚡ Velocidad", callback_data="speed_menu")]
    ]

    await update.message.reply_text(
        "🤖 BOT INTÉRPRETE BILINGÜE\n\n"
        "Modo conversación automática entre Español ↔ Inglés\n\n"
        "Selecciona una opción:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def accent_menu(update, context):
    kb = [[InlineKeyboardButton(v, callback_data=f"accent_{k}")]
          for k, v in AVAILABLE_ACCENTS.items()]
    await update.callback_query.edit_message_text(
        "Selecciona idioma de voz:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def speed_menu(update, context):
    kb = [[InlineKeyboardButton(v['name'], callback_data=f"speed_{k}")]
          for k, v in SPEED_OPTIONS.items()]
    await update.callback_query.edit_message_text(
        "Selecciona velocidad:",
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
        await q.edit_message_text(f"🎧 Modo conversación bilingüe: {estado}")

    elif q.data.startswith("accent_"):
        user_preferences[uid]['accent'] = q.data.replace("accent_", "")
        await q.edit_message_text("✅ Idioma de voz actualizado")

    elif q.data.startswith("speed_"):
        user_preferences[uid]['speed'] = q.data.replace("speed_", "")
        await q.edit_message_text("✅ Velocidad actualizada")

# ================= AUDIO =================
async def handle_voice(update, context):
    uid = update.effective_user.id
    if not user_preferences.get(uid, {}).get("bilingual"):
        return

    voice = await context.bot.get_file(update.message.voice.file_id)
    audio_bytes = await voice.download_as_bytearray()

    try:
        text = speech_to_text(audio_bytes)
    except:
        await update.message.reply_text("No pude reconocer el audio.")
        return

    lang = detect_language(text)

    if lang == "es":
        translated = translate_text(text, "en")
        audio = tts(translated, "en")
    else:
        translated = translate_text(text, "es")
        audio = tts(translated, "es")

    await update.message.reply_voice(audio)

# ================= MAIN =================
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TOKEN NO CONFIGURADO")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()

if __name__ == "__main__":
    main()
