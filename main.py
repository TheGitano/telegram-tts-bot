import os
import io
import logging
import asyncio
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

FIRMA_TEXTO = "¡¡ Esto fue realizado por 🦅𝓣𝓽ͭ𝓱ͪ𝓮ͤ𝓖𝓲𝓽ͭ𝓪ͣ𝓷𝓸 🦅 !!"

AVAILABLE_ACCENTS = {
    'es-us': '🇲🇽 Español Latino',
    'es-ar': '🇦🇷 Argentina',
    'es-es': '🇪🇸 España'
}

SPEED_OPTIONS = {
    'lento': {'speed': True, 'name': '🐌 Lento'},
    'normal': {'speed': False, 'name': '✅ Normal'}
}

user_preferences = {}
pending_docs = {}

# ================= LOG =================
logging.basicConfig(level=logging.INFO)

# ================= UTILIDADES =================
def detect_language(text):
    try:
        return detect(text)
    except:
        return 'unknown'

def translate_to_spanish(text):
    return GoogleTranslator(source='auto', target='es').translate(text)

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def tts(text, accent, slow):
    tts = gTTS(text=text, lang=accent, slow=slow)
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
        "Convierte texto a voz\n"
        "Lee archivos PDF y Word\n"
        "Traduce automáticamente a español latino\n"
        "Múltiples acentos\n"
        "Velocidad ajustable\n"
        "🎧 Conversación bilingüe por audio\n\n"
        "Comandos:\n"
        "/start - Ver este mensaje\n"
        "/help - Ayuda\n"
        "/config - Configuración\n"
        "/accent - Cambiar acento\n"
        "/speed - Cambiar velocidad\n"
    )

async def help_command(update, context):
    await update.message.reply_text(
        "Envíame texto, PDF, Word o audio.\n"
        "El bot traducirá todo al español latino automáticamente.\n"
    )

async def accent_command(update, context):
    kb = [[InlineKeyboardButton(v, callback_data=f"accent_{k}")]
          for k, v in AVAILABLE_ACCENTS.items()]
    await update.message.reply_text("Selecciona acento:", reply_markup=InlineKeyboardMarkup(kb))

async def speed_command(update, context):
    kb = [[InlineKeyboardButton(v['name'], callback_data=f"speed_{k}")]
          for k, v in SPEED_OPTIONS.items()]
    await update.message.reply_text("Selecciona velocidad:", reply_markup=InlineKeyboardMarkup(kb))

async def config_command(update, context):
    uid = update.effective_user.id
    auto = user_preferences.get(uid, {}).get('auto', True)
    bilingual = user_preferences.get(uid, {}).get('bilingual', False)

    kb = [
        [InlineKeyboardButton("Traducción automática: " + ("ON" if auto else "OFF"), callback_data="auto")],
        [InlineKeyboardButton("🎧 Modo intérprete: " + ("ON" if bilingual else "OFF"), callback_data="bilingual")]
    ]

    await update.message.reply_text("Configuración:", reply_markup=InlineKeyboardMarkup(kb))

# ================= BOTONES =================
async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {'auto': True})

    if q.data == "auto":
        user_preferences[uid]['auto'] = not user_preferences[uid]['auto']
        await q.edit_message_text("Configuración actualizada")

    elif q.data == "bilingual":
        user_preferences[uid]['bilingual'] = not user_preferences[uid].get('bilingual', False)
        await q.edit_message_text("Modo intérprete actualizado")

    elif q.data.startswith("accent_"):
        user_preferences[uid]['accent'] = q.data.replace("accent_", "")
        await q.edit_message_text("Acento actualizado")

    elif q.data.startswith("speed_"):
        user_preferences[uid]['speed'] = q.data.replace("speed_", "")
        await q.edit_message_text("Velocidad actualizada")

    elif q.data == "doc_yes":
        file = pending_docs.pop(uid)
        await process_document(update, context, file)

    elif q.data == "doc_no":
        pending_docs.pop(uid)
        await q.edit_message_text("Documento cancelado.")

# ================= TEXTO =================
async def handle_text(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {'auto': True})

    text = update.message.text

    if user_preferences[uid]['auto']:
        text = translate_to_spanish(text)

    accent = user_preferences.get(uid, {}).get('accent', 'es-us')
    speed = user_preferences.get(uid, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed]['speed']

    audio = tts(text, accent, slow)
    await update.message.reply_voice(audio)
    await update.message.reply_text(FIRMA_TEXTO)

# ================= DOCUMENTOS =================
async def handle_doc(update, context):
    uid = update.effective_user.id
    pending_docs[uid] = update.message.document

    kb = [
        [InlineKeyboardButton("✅ SI", callback_data="doc_yes")],
        [InlineKeyboardButton("❌ NO", callback_data="doc_no")]
    ]

    await update.message.reply_text(
        "⚠️ Este documento será traducido al español.\n"
        "⏳ La traducción será eliminada en 24hs.\n\n"
        "¿Deseas continuar?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def process_document(update, context, doc):
    uid = update.effective_user.id
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    stream = io.BytesIO(data)

    if doc.file_name.endswith('.pdf'):
        text = extract_text_from_pdf(stream)
    else:
        text = extract_text_from_docx(stream)

    text = translate_to_spanish(text)

    accent = user_preferences.get(uid, {}).get('accent', 'es-us')
    speed = user_preferences.get(uid, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed]['speed']

    audio = tts(text, accent, slow)
    await update.callback_query.message.reply_voice(audio)
    await update.callback_query.message.reply_text(FIRMA_TEXTO)

# ================= AUDIO INTÉRPRETE =================
async def handle_voice(update, context):
    uid = update.effective_user.id
    if not user_preferences.get(uid, {}).get("bilingual"):
        return

    voice = await context.bot.get_file(update.message.voice.file_id)
    audio_bytes = await voice.download_as_bytearray()

    text = speech_to_text(audio_bytes)
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
