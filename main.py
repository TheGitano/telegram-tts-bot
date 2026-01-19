import os
import logging
import io
import subprocess
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
import whisper

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

FIRMA_TEXTO = "¡¡ Esto fue realizado por 🦅𝓣𝓽ͭ𝓱ͪ𝓮ͤ𝓖𝓲𝓽ͭ𝓪ͣ𝓷𝓸 🦅 !!"

model = whisper.load_model("base")

user_preferences = {}

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= UTILIDADES =================

def translate_text(text, target):
    translator = GoogleTranslator(source='auto', target=target)
    return translator.translate(text)

def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"

def tts(text, lang="es"):
    tts = gTTS(text=text, lang=lang)
    audio = io.BytesIO()
    tts.write_to_fp(audio)
    audio.seek(0)
    return audio

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def convert_ogg_to_wav(ogg_path, wav_path):
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def transcribe_audio(path):
    result = model.transcribe(path)
    return result["text"]

# ================= MENÚ =================

async def show_main_menu(update, context):
    kb = [
        [InlineKeyboardButton("🎧 Conversación bilingüe (INTÉRPRETE)", callback_data="menu_interpreter")],
        [InlineKeyboardButton("📄 Traducir PDF o Word", callback_data="menu_docs")],
        [InlineKeyboardButton("📝 Texto a Voz", callback_data="menu_text")],
        [InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")]
    ]

    text = (
        "🎙 BOT INTÉRPRETE PRO\n\n"
        "Selecciona una opción:"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def interpreter_menu(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})
    status = user_preferences[uid].get("interpreter", False)

    status_text = "✅ ACTIVADO" if status else "❌ DESACTIVADO"
    toggle_text = "❌ DESACTIVAR" if status else "✅ ACTIVAR"

    kb = [
        [InlineKeyboardButton(toggle_text, callback_data="toggle_interpreter")],
        [InlineKeyboardButton("⬅ Volver", callback_data="back_menu")]
    ]

    text = (
        "🎧 MODO INTÉRPRETE\n\n"
        "Traducción por voz en tiempo real\n"
        "Español ⇄ Inglés\n\n"
        f"Estado: {status_text}"
    )

    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))

# ================= BOTONES =================

async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})

    if q.data == "menu_interpreter":
        await interpreter_menu(update, context)

    elif q.data == "menu_docs":
        await q.edit_message_text("📄 Envíame un archivo PDF o Word para traducirlo.")

    elif q.data == "menu_text":
        await q.edit_message_text("📝 Escríbeme el texto que deseas convertir a audio.")

    elif q.data == "menu_help":
        await q.edit_message_text(
            "❓ Ayuda\n\n"
            "• Envía texto para convertir a voz\n"
            "• Envía audio para traducir\n"
            "• Activa modo intérprete para conversar"
        )

    elif q.data == "toggle_interpreter":
        user_preferences[uid]["interpreter"] = not user_preferences[uid].get("interpreter", False)
        await interpreter_menu(update, context)

    elif q.data == "back_menu":
        await show_main_menu(update, context)

# ================= COMANDOS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

# ================= TEXTO =================

async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text

    audio = tts(text, "es")
    await update.message.reply_voice(audio)
    await update.message.reply_text(FIRMA_TEXTO)

# ================= DOCUMENTOS =================

async def handle_doc(update, context):
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    stream = io.BytesIO(data)

    if doc.file_name.endswith('.pdf'):
        text = extract_text_from_pdf(stream)
    else:
        text = extract_text_from_docx(stream)

    translated = translate_text(text, "es")
    audio = tts(translated, "es")

    await update.message.reply_voice(audio)
    await update.message.reply_text(FIRMA_TEXTO)

# ================= AUDIO =================

async def handle_voice(update, context):
    uid = update.effective_user.id
    prefs = user_preferences.get(uid, {})

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)

    ogg_path = f"/tmp/{voice.file_id}.ogg"
    wav_path = f"/tmp/{voice.file_id}.wav"

    await file.download_to_drive(ogg_path)
    convert_ogg_to_wav(ogg_path, wav_path)

    text = transcribe_audio(wav_path)

    if prefs.get("interpreter"):
        lang = detect_language(text)
        target = "es" if lang == "en" else "en"
        translated = translate_text(text, target)
        audio = tts(translated, target)
        await update.message.reply_voice(audio)
    else:
        audio = tts(text, "es")
        await update.message.reply_voice(audio)
        await update.message.reply_text(FIRMA_TEXTO)

# ================= MAIN =================

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TOKEN NO CONFIGURADO")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()

if __name__ == "__main__":
    main()
