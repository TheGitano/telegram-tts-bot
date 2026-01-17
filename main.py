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
FIRMA = "Esto fue realizado por El Gitano Traducciones"

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
logger = logging.getLogger(__name__)

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
    tts = gTTS(text=text, lang=accent, slow=slow)
    audio = io.BytesIO()
    tts.write_to_fp(audio)
    audio.seek(0)
    return audio

# ================= COMANDOS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 Bot TTS gratuito\n"
        f"Texto, PDF y Word\n"
        f"/accent /speed /config\n\n{FIRMA}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Envía texto o documentos.\n"
        f"Audio ilimitado.\n\n{FIRMA}"
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
    kb = [[InlineKeyboardButton("✅ ON" if auto else "❌ OFF", callback_data="auto")]]
    await update.message.reply_text(
        f"Traducción automática: {'ON' if auto else 'OFF'}",
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
        await q.edit_message_text(f"✅ Acento cambiado\n{FIRMA}")

    elif q.data.startswith("speed_"):
        user_preferences[uid]['speed'] = q.data.replace("speed_", "")
        await q.edit_message_text(f"✅ Velocidad cambiada\n{FIRMA}")

    elif q.data == "auto":
        user_preferences[uid]['auto'] = not user_preferences[uid].get('auto', False)
        await q.edit_message_text(f"✅ Configuración actualizada\n{FIRMA}")

# ================= MENSAJES =================
async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text
    if detect_language(text) != 'es' and user_preferences.get(uid, {}).get('auto'):
        text = translate_text(text)
    audio = tts(text, uid)
    await update.message.reply_voice(audio)
    await update.message.reply_text(FIRMA)

async def handle_doc(update, context):
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()
    stream = io.BytesIO(data)
    text = extract_text_from_pdf(stream) if doc.file_name.endswith('.pdf') else extract_text_from_docx(stream)
    audio = tts(text, update.effective_user.id)
    await update.message.reply_voice(audio)
    await update.message.reply_text(FIRMA)

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

    app.run_polling()

if __name__ == "__main__":
    main()
