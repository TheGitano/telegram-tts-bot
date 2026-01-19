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
    'es-es': '🇪🇸 España',
    'es-us': '🇲🇽 Latino',
    'es-mx': '🇲🇽 México',
    'es-ar': '🇦🇷 Argentina',
    'es-co': '🇨🇴 Colombia',
    'es-cl': '🇨🇱 Chile',
    'es': '🌎 Español'
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

# ================= UTILIDADES =================
def detect_language(text):
    try:
        return detect(text)
    except:
        return 'unknown'

def translate_text(text):
    try:
        translator = GoogleTranslator(source='auto', target='es')
        if len(text) > 4500:
            parts = [text[i:i+4500] for i in range(0, len(text), 4500)]
            return ' '.join(translator.translate(p) for p in parts)
        return translator.translate(text)
    except:
        return text

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join(page.extract_text() or "" for page in reader.pages[:20])

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def tts(text, user_id):
    accent = user_preferences.get(user_id, {}).get('accent', 'es-us')
    speed = user_preferences.get(user_id, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed]['speed']
    tts = gTTS(text=f"{text}\n\n{FIRMA}", lang=accent, slow=slow)
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
    await update.message.reply_text(
        "¡Hola! Soy tu bot de Text-to-Speech 100% GRATUITO\n\n"
        "Funcionalidades:\n"
        "Convierte texto a voz (GRATIS, sin límites)\n"
        "Lee archivos PDF y Word\n"
        "Traduce automáticamente a español\n"
        "Múltiples acentos latinos disponibles\n"
        "Velocidad ajustable\n"
        "🎧 Conversación bilingüe por audio\n\n"
        "Cómo usarme:\n"
        "Envíame texto directamente\n"
        "Envíame un archivo PDF o Word (.docx)\n"
        "Envíame un audio (modo bilingüe)\n\n"
        "Comandos:\n"
        "/start - Ver este mensaje\n"
        "/help - Ayuda detallada\n"
        "/config - Traducción automática\n"
        "/accent - Cambiar acento\n"
        "/speed - Ajustar velocidad\n\n"
        "100% GRATUITO - Sin límites ni API Keys\n\n"
        f"{FIRMA}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Envía texto o documentos.\n"
        "Envía audio para conversación bilingüe.\n"
        "Audio ilimitado.\n\n"
        f"{FIRMA}"
    )

async def accent_command(update, context):
    kb = [[InlineKeyboardButton(v, callback_data=f"accent_{k}")]
          for k, v in AVAILABLE_ACCENTS.items()]
    await update.message.reply_text(
        "Selecciona acento:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def speed_command(update, context):
    kb = [[InlineKeyboardButton(v['name'], callback_data=f"speed_{k}")]
          for k, v in SPEED_OPTIONS.items()]
    await update.message.reply_text(
        "Selecciona velocidad:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def config_command(update, context):
    uid = update.effective_user.id
    auto = user_preferences.get(uid, {}).get('auto', False)
    bilingual = user_preferences.get(uid, {}).get('bilingual', False)

    kb = [
        [InlineKeyboardButton("Traducción automática: " + ("ON" if auto else "OFF"), callback_data="auto")],
        [InlineKeyboardButton("🎧 Conversación bilingüe: " + ("ON" if bilingual else "OFF"), callback_data="bilingual")]
    ]

    await update.message.reply_text(
        "Configuración:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= BOTONES =================
async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})

    if q.data.startswith("accent_"):
        user_preferences[uid]['accent'] = q.data.replace("accent_", "")
        await q.edit_message_text("Acento cambiado correctamente")

    elif q.data.startswith("speed_"):
        user_preferences[uid]['speed'] = q.data.replace("speed_", "")
        await q.edit_message_text("Velocidad cambiada correctamente")

    elif q.data == "auto":
        user_preferences[uid]['auto'] = not user_preferences[uid].get('auto', False)
        estado = "ON" if user_preferences[uid]['auto'] else "OFF"
        await q.edit_message_text(f"Traducción automática: {estado}")

    elif q.data == "bilingual":
        user_preferences[uid]['bilingual'] = not user_preferences[uid].get('bilingual', False)
        estado = "ON" if user_preferences[uid]['bilingual'] else "OFF"
        await q.edit_message_text(f"Conversación bilingüe: {estado}")

# ================= MENSAJES =================
async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text

    if detect_language(text) != 'es' and user_preferences.get(uid, {}).get('auto'):
        text = translate_text(text)

    audio = tts(text, uid)
    await update.message.reply_voice(audio)

async def handle_doc(update, context):
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    stream = io.BytesIO(data)

    if doc.file_name.endswith('.pdf'):
        text = extract_text_from_pdf(stream)
    else:
        text = extract_text_from_docx(stream)

    uid = update.effective_user.id
    audio = tts(text, uid)
    await update.message.reply_voice(audio)

# ================= AUDIO BILINGÜE =================
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
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        audio = gTTS(translated, lang="en")
    else:
        translated = GoogleTranslator(source='auto', target='es').translate(text)
        audio = gTTS(translated, lang="es")

    out = io.BytesIO()
    audio.write_to_fp(out)
    out.seek(0)

    await update.message.reply_voice(out)

# ================= MAIN =================
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TOKEN NO CONFIGURADO")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("accent", accent_command))
    app.add_handler(CommandHandler("speed", speed_command))
    app.add_handler(CommandHandler("config", config_command))

    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()

if __name__ == "__main__":
    main()
