import os
import logging
import io
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
    'normal': {'speed': False, 'name': 'Normal'},
    'lento': {'speed': True, 'name': 'Lento'}
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

def translate_text(text, target='es'):
    translator = GoogleTranslator(source='auto', target=target)
    return translator.translate(text)

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def tts(text, user_id):
    prefs = user_preferences.get(user_id, {})
    accent = prefs.get('accent', 'es-us')
    speed = prefs.get('speed', 'normal')
    slow = SPEED_OPTIONS[speed]['speed']

    tts = gTTS(text=text, lang=accent, slow=slow)
    audio = io.BytesIO()
    tts.write_to_fp(audio)
    audio.seek(0)
    return audio

# ================= MENÚ PRINCIPAL =================

async def show_main_menu(update, context):
    kb = [
        [InlineKeyboardButton("🎧 Conversación bilingüe (INTÉRPRETE)", callback_data="menu_interpreter")],
        [InlineKeyboardButton("📄 Traducir PDF o Word", callback_data="menu_docs")],
        [InlineKeyboardButton("📝 Texto a Voz", callback_data="menu_text")],
        [InlineKeyboardButton("⚙ Configuración", callback_data="menu_config")],
        [InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")]
    ]

    text = (
        "🎙 *BOT TEXT TO SPEECH PRO — 100% GRATIS*\n\n"
        "Selecciona una opción:"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================= MENÚ INTÉRPRETE =================

async def interpreter_menu(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})
    status = user_preferences[uid].get("bilingual", False)

    status_text = "✅ ACTIVADO" if status else "❌ DESACTIVADO"
    toggle_text = "❌ DESACTIVAR INTÉRPRETE" if status else "✅ ACTIVAR INTÉRPRETE"

    kb = [
        [InlineKeyboardButton(toggle_text, callback_data="toggle_interpreter")],
        [InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]
    ]

    text = (
        "🎧 *MODO INTÉRPRETE*\n\n"
        "Convierte audio automáticamente:\n"
        "🇪🇸 Español ⇄ Inglés\n\n"
        f"Estado actual: {status_text}"
    )

    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================= CONFIG =================

async def config_menu(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})
    auto = user_preferences[uid].get('auto', True)

    auto_text = "ON" if auto else "OFF"

    kb = [
        [InlineKeyboardButton(f"🌎 Traducción automática: {auto_text}", callback_data="toggle_auto")],
        [InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]
    ]

    text = "⚙ *Configuración del bot*"

    await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================= COMANDOS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_main_menu(update, context)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ Ayuda\n\n"
        "• Envia texto para convertir a voz\n"
        "• Envia PDF o Word para traducir\n"
        "• Usa el modo intérprete para conversar\n\n"
        "100% GRATIS — Sin límites"
    )

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
        await q.edit_message_text("📝 Escríbeme el texto que deseas convertir a voz.")

    elif q.data == "menu_config":
        await config_menu(update, context)

    elif q.data == "menu_help":
        await q.edit_message_text(
            "❓ Ayuda\n\n"
            "Envía texto o documentos.\n"
            "Usa el modo intérprete para conversar."
        )

    elif q.data == "toggle_interpreter":
        user_preferences[uid]["bilingual"] = not user_preferences[uid].get("bilingual", False)
        await interpreter_menu(update, context)

    elif q.data == "toggle_auto":
        user_preferences[uid]["auto"] = not user_preferences[uid].get("auto", True)
        await config_menu(update, context)

    elif q.data == "back_menu":
        await show_main_menu(update, context)

# ================= MENSAJES =================

async def handle_text(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})
    text = update.message.text

    if user_preferences[uid].get("bilingual"):
        lang = detect_language(text)
        target = "es" if lang == "en" else "en"
        text = translate_text(text, target)

    elif user_preferences[uid].get("auto", True):
        if detect_language(text) != 'es':
            text = translate_text(text, 'es')

    audio = tts(text, uid)
    await update.message.reply_voice(audio)
    await update.message.reply_text(FIRMA_TEXTO)

async def handle_doc(update, context):
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    stream = io.BytesIO(data)

    if doc.file_name.endswith('.pdf'):
        text = extract_text_from_pdf(stream)
    else:
        text = extract_text_from_docx(stream)

    text = translate_text(text, 'es')
    audio = tts(text, uid)

    await update.message.reply_voice(audio)
    await update.message.reply_text(FIRMA_TEXTO)

# ================= MAIN =================

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TOKEN NO CONFIGURADO")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    app.run_polling()

if __name__ == "__main__":
    main()
