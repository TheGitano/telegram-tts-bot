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
import asyncio

# ===== CONFIG =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))  # Opcional: para recibir logs de errores
FIRMA = "By🦅𝓣𝓽ͭ𝓱ͪ𝓮ͤ𝓖𝓲𝓽ͭ𝓪ͣ𝓷𝓸 🦅"

AVAILABLE_ACCENTS = {
    'es-es': '🇪🇸 España',
    'es-us': '🇲🇽 Latino (México)',
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

# ===== LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== FUNCIONES DE UTILIDAD =====
def detect_language(text: str) -> str:
    try:
        return detect(text)
    except:
        return 'unknown'

def translate_text(text: str, target_lang='es') -> str:
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        if len(text) > 4500:
            chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
            return ' '.join([translator.translate(c) for c in chunks])
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Error traduciendo: {e}")
        return text

def extract_text_from_pdf(pdf_file) -> str:
    pdf_reader = PyPDF2.PdfReader(pdf_file)
    text = ""
    for page in pdf_reader.pages[:20]:
        text += page.extract_text() + "\n"
    return text.strip()

def extract_text_from_docx(docx_file) -> str:
    doc = Document(docx_file)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text.strip()

def text_to_speech_gtts(text: str, user_id: int) -> bytes:
    accent = user_preferences.get(user_id, {}).get('accent', 'es-us')
    speed_setting = user_preferences.get(user_id, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed_setting]['speed']
    tts = gTTS(text=text + f"\n\n{FIRMA}", lang=accent, slow=slow)
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)
    return audio_fp.read()

async def generate_and_send_audio(message, text: str, context, user_id: int):
    if len(text) > 10000:
        text = text[:10000]
        await message.reply_text("⚠ Texto muy largo, procesaré los primeros 10,000 caracteres.")
    processing_msg = await message.reply_text("🎤 Generando audio...")
    try:
        audio_data = text_to_speech_gtts(text, user_id)
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.mp3"
        await message.reply_voice(voice=audio_file, caption=f"🔊 Audio generado\n{FIRMA}")
        await processing_msg.delete()
        logger.info(f"Audio generado para usuario {user_id}")
    except Exception as e:
        logger.error(f"Error generando audio: {e}")
        await processing_msg.edit_text(f"❌ Error al generar audio.\nDetalles: {str(e)}")
        if ADMIN_ID:
            try:
                await context.bot.send_message(ADMIN_ID, f"❌ Error TTS: {str(e)}")
            except: pass

# ===== COMANDOS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"¡Hola! Soy tu bot de TTS gratuito.\nComandos: /help /accent /speed /config\n\n{FIRMA}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Guía rápida:\n- Envía texto o PDF/Word\n- Traducción automática\n- Ajusta acento y velocidad\n\n{FIRMA}"
    )

async def accent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(name, callback_data=f"accent_{key}")] for key, name in AVAILABLE_ACCENTS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    user_id = update.effective_user.id
    await update.message.reply_text(f"Selecciona un acento:\n{FIRMA}", reply_markup=reply_markup)

async def speed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(info['name'], callback_data=f"speed_{key}")] for key, info in SPEED_OPTIONS.items()]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Selecciona velocidad:\n{FIRMA}", reply_markup=reply_markup)

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    auto_translate = user_preferences.get(user_id, {}).get('auto_translate', False)
    keyboard = [[InlineKeyboardButton("✅ ON" if auto_translate else "⬜ OFF", callback_data="toggle_auto_translate")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Traducción automática: {'✅ ON' if auto_translate else '❌ OFF'}\n{FIRMA}", reply_markup=reply_markup)

# ===== BOTONES =====
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    if user_id not in user_preferences:
        user_preferences[user_id] = {}
    if query.data.startswith('accent_'):
        accent = query.data.replace('accent_', '')
        user_preferences[user_id]['accent'] = accent
        await query.edit_message_text(f"✅ Acento cambiado a {AVAILABLE_ACCENTS.get(accent, accent)}\n{FIRMA}")
    elif query.data.startswith('speed_'):
        speed = query.data.replace('speed_', '')
        user_preferences[user_id]['speed'] = speed
        await query.edit_message_text(f"✅ Velocidad ajustada a {SPEED_OPTIONS[speed]['name']}\n{FIRMA}")
    elif query.data == 'toggle_auto_translate':
        current = user_preferences[user_id].get('auto_translate', False)
        user_preferences[user_id]['auto_translate'] = not current
        await query.edit_message_text(f"Traducción automática: {'✅ ON' if not current else '❌ OFF'}\n{FIRMA}")

# ===== MENSAJES =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    auto_translate = user_preferences.get(user_id, {}).get('auto_translate', False)
    detected_lang = detect_language(user_text)
    if detected_lang != 'es' and detected_lang != 'unknown' and auto_translate:
        user_text = translate_text(user_text)
    await generate_and_send_audio(update.message, user_text, context, user_id)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name.lower()
    user_id = update.effective_user.id
    if not (file_name.endswith('.pdf') or file_name.endswith('.docx')):
        await update.message.reply_text("❌ Solo PDF o Word (.docx)")
        return
    file = await context.bot.get_file(document.file_id)
    file_bytes = await file.download_as_bytearray()
    file_stream = io.BytesIO(file_bytes)
    if file_name.endswith('.pdf'):
        text = extract_text_from_pdf(file_stream)
    else:
        text = extract_text_from_docx(file_stream)
    if text:
        await generate_and_send_audio(update.message, text, context, user_id)
    else:
        await update.message.reply_text(f"❌ No se pudo extraer texto\n{FIRMA}")

# ===== ERROR HANDLER =====
async def error_handler(update, context):
    logger.error(f"Ocurrió un error: {context.error}")
    if ADMIN_ID:
        try:
            await context.bot.send_message(ADMIN_ID, f"❌ Error crítico: {context.error}")
        except: pass
    try:
        if update and update.message:
            await update.message.reply_text(f"❌ Error inesperado\n{FIRMA}")
    except: pass

# ===== MAIN =====
def main():
    if not TELEGRAM_BOT_TOKEN or len(TELEGRAM_BOT_TOKEN) < 30:
        print("❌ TELEGRAM_BOT_TOKEN no configurado correctamente")
        return

    print("🤖 Bot definitivo iniciado (Producción Railway)")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    # comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("accent", accent_command))
    application.add_handler(CommandHandler("speed", speed_command))
    application.add_handler(CommandHandler("config", config_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    # mensajes
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.FileExtension("docx"), handle_document))
    # errores
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
