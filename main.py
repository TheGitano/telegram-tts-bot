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
from docx.shared import Pt
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

def translate_text(text, target="es"):
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

def convert_ogg_to_wav(ogg_path, wav_path):
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def transcribe_audio(path):
    result = model.transcribe(path)
    return result["text"]

def translate_docx(file_bytes, target="es"):
    doc = Document(io.BytesIO(file_bytes))
    for p in doc.paragraphs:
        p.text = translate_text(p.text, target)
    out_stream = io.BytesIO()
    doc.save(out_stream)
    out_stream.seek(0)
    return out_stream

# ================= MENÚ =================

async def show_main_menu(update, context):
    kb = [
        [InlineKeyboardButton("🎧 Conversación bilingüe (Intérprete)", callback_data="menu_interpreter")],
        [InlineKeyboardButton("🗣 Traductor de voz", callback_data="menu_voice_translator")],
        [InlineKeyboardButton("📄 Traducir documentos (Word/PDF)", callback_data="menu_docs")],
        [InlineKeyboardButton("📝 Texto a voz", callback_data="menu_text")],
        [InlineKeyboardButton("⚙ Configuración", callback_data="menu_config")],
        [InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")]
    ]

    text = (
        "🎙 *Bienvenido!*\n\n"
        "Este bot ha sido creado por *El Gitano* para ayudarte a:\n"
        "• Traducir texto a español latino\n"
        "• Traducir audios (Inglés ⇄ Español)\n"
        "• Traducir documentos Word o PDF y mantener su formato\n"
        "• Conversar en modo intérprete bilingüe\n"
        "• Convertir texto a voz con acento latino\n\n"
        "Selecciona una opción:"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def interpreter_menu(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})
    status = user_preferences[uid].get("interpreter", False)

    status_text = "✅ ACTIVADO" if status else "❌ DESACTIVADO"
    toggle_text = "❌ DESACTIVAR" if status else "✅ ACTIVAR"

    kb = [
        [InlineKeyboardButton(toggle_text, callback_data="toggle_interpreter")],
        [InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]
    ]

    text = (
        "🎧 *Modo Intérprete*\n"
        "Traduce audio en tiempo real\n"
        "Español ⇄ Inglés\n"
        f"Estado: {status_text}"
    )
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def config_menu(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})
    auto = user_preferences[uid].get('auto', True)
    auto_text = "✅ ON" if auto else "❌ OFF"

    kb = [
        [InlineKeyboardButton(f"🌎 Traducción automática: {auto_text}", callback_data="toggle_auto")],
        [InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]
    ]

    text = "⚙ *Configuración del Bot*"
    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================= BOTONES =================

async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})

    if q.data == "menu_interpreter":
        await interpreter_menu(update, context)
    elif q.data == "menu_voice_translator":
        await q.edit_message_text("🗣 Envíame un audio para traducir (Inglés ⇄ Español).")
    elif q.data == "menu_docs":
        await q.edit_message_text("📄 Envíame un documento Word o PDF para traducirlo sin afectar el formato.")
    elif q.data == "menu_text":
        await q.edit_message_text("📝 Escribe el texto que quieres convertir a audio.")
    elif q.data == "menu_help":
        await q.edit_message_text(
            "❓ *Ayuda*\n"
            "• Envía texto para convertir a voz\n"
            "• Envía documentos o audio para traducir\n"
            "• Activa modo intérprete para conversación bilingüe",
            parse_mode="Markdown"
        )
    elif q.data == "toggle_interpreter":
        user_preferences[uid]["interpreter"] = not user_preferences[uid].get("interpreter", False)
        await interpreter_menu(update, context)
    elif q.data == "toggle_auto":
        user_preferences[uid]["auto"] = not user_preferences[uid].get("auto", True)
        await config_menu(update, context)
    elif q.data == "back_menu":
        await show_main_menu(update, context)

# ================= COMANDOS =================

async def start(update, context):
    await show_main_menu(update, context)

# ================= TEXTO =================

async def handle_text(update, context):
    audio = tts(update.message.text, "es")
    await update.message.reply_voice(audio)
    kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
    await update.message.reply_text(FIRMA_TEXTO, reply_markup=InlineKeyboardMarkup(kb))

# ================= DOCUMENTOS =================

async def handle_doc(update, context):
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()

    if doc.file_name.endswith(".docx"):
        translated_file = translate_docx(data, "es")
        await update.message.reply_document(document=translated_file, filename=f"traducido_{doc.file_name}")
    else:
        # Para PDFs, se devuelve como audio TTS del contenido traducido
        text = extract_text_from_pdf(io.BytesIO(data))
        translated_text = translate_text(text, "es")
        audio = tts(translated_text, "es")
        await update.message.reply_voice(audio)

    kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
    await update.message.reply_text(FIRMA_TEXTO, reply_markup=InlineKeyboardMarkup(kb))

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
    lang = detect_language(text)

    # Traducción automática si inglés o modo intérprete activado
    if lang == "en" or prefs.get("interpreter"):
        translated = translate_text(text, "es")
        audio = tts(translated, "es")
        await update.message.reply_voice(audio)
    else:
        audio = tts(text, "es")
        await update.message.reply_voice(audio)

    kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
    await update.message.reply_text(FIRMA_TEXTO, reply_markup=InlineKeyboardMarkup(kb))

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
