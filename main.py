import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import io
from docx import Document
import PyPDF2
from deep_translator import GoogleTranslator
from langdetect import detect
from gtts import gTTS

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== CONFIGURACIÓN =====
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIRMA = "By🦅𝓣𝓽ͭ𝓱ͪ𝓮ͤ𝓖𝓲𝓽ͭ𝓪ͣ𝓷𝓸 🦅"

AVAILABLE_ACCENTS = {
    'es-es': '🇪🇸 Español de España',
    'es-us': '🇲🇽 Español Latino (México)',
    'es-mx': '🇲🇽 Español de México',
    'es-ar': '🇦🇷 Español de Argentina',
    'es-co': '🇨🇴 Español de Colombia',
    'es-cl': '🇨🇱 Español de Chile',
    'es': '🌎 Español General'
}

SPEED_OPTIONS = {
    'lento': {'speed': True, 'name': '🐌 Lento'},
    'normal': {'speed': False, 'name': '✅ Normal'}
}

user_preferences = {}

# ===== FUNCIONES =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"¡Hola! Soy tu bot de Text-to-Speech 100% GRATUITO\n\n"
        "Funcionalidades:\n"
        "- Convierte texto a voz\n"
        "- Lee archivos PDF y Word\n"
        "- Traduce automáticamente a español\n"
        "- Múltiples acentos latinos\n"
        "- Velocidad ajustable\n\n"
        "Comandos:\n"
        "/start - Ver este mensaje\n"
        "/help - Ayuda detallada\n"
        "/config - Traducción automática\n"
        "/accent - Cambiar acento\n"
        "/speed - Ajustar velocidad\n\n"
        f"{FIRMA}"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Guía completa del bot:\n\n"
        "Texto: Envía cualquier texto y lo convertiré a audio.\n"
        "Archivos PDF: Extraigo el texto y lo leo.\n"
        "Archivos Word (.docx): Procesa documentos Word.\n"
        "Traducción: Detecto idioma automáticamente y traduzco si quieres.\n"
        "Personalización: /accent para cambiar acento, /speed para velocidad.\n\n"
        f"{FIRMA}"
    )

# ===== Funciones de TTS =====
def text_to_speech_gtts(text: str, user_id: int) -> bytes:
    accent = user_preferences.get(user_id, {}).get('accent', 'es-us')
    speed_setting = user_preferences.get(user_id, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed_setting]['speed']

    tts = gTTS(text=text + f"\n\n{FIRMA}", lang=accent, slow=slow)
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)
    return audio_fp.read()

async def generate_and_send_audio(message, text: str, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    if len(text) > 10000:
        text = text[:10000]
        await message.reply_text("⚠ El texto es muy largo. Procesaré los primeros 10,000 caracteres.")

    processing_msg = await message.reply_text("🎤 Generando audio...")
    try:
        max_chunk_size = 5000
        if len(text) > max_chunk_size:
            chunks = [text[i:i+max_chunk_size] for i in range(0, len(text), max_chunk_size)]
            for idx, chunk in enumerate(chunks[:3], 1):
                audio_data = text_to_speech_gtts(chunk, user_id)
                audio_file = io.BytesIO(audio_data)
                audio_file.name = f"audio_parte_{idx}.mp3"

                await message.reply_voice(
                    voice=audio_file,
                    caption=f"🔊 Parte {idx}/{min(len(chunks),3)} ({len(chunk)} caracteres)\n{FIRMA}"
                )

            if len(chunks) > 3:
                await message.reply_text(f"ℹ El documento tiene más partes. Se procesaron las primeras 3 ({max_chunk_size*3} caracteres).")
        else:
            audio_data = text_to_speech_gtts(text, user_id)
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.mp3"
            await message.reply_voice(
                voice=audio_file,
                caption=f"🔊 Audio generado ({len(text)} caracteres)\n{FIRMA}"
            )
        await processing_msg.delete()
        logger.info(f"Audio generado exitosamente para usuario {user_id}")
    except Exception as e:
        logger.error(f"Error al generar audio: {e}")
        await processing_msg.edit_text(f"❌ Error al generar el audio.\nDetalles: {str(e)}")

# ===== Funciones de documentos =====
def extract_text_from_pdf(pdf_file) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        max_pages = min(len(pdf_reader.pages), 20)
        for page_num in range(max_pages):
            page = pdf_reader.pages[page_num]
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extrayendo texto de PDF: {e}")
        raise

def extract_text_from_docx(docx_file) -> str:
    try:
        doc = Document(docx_file)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error extrayendo texto de Word: {e}")
        raise

# ===== Detección y traducción =====
def detect_language(text: str) -> str:
    try:
        return detect(text)
    except:
        return 'unknown'

def translate_text(text: str, target_lang: str = 'es') -> str:
    try:
        translator = GoogleTranslator(source='auto', target=target_lang)
        if len(text) > 4500:
            chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
            translated_chunks = [translator.translate(chunk) for chunk in chunks]
            return ' '.join(translated_chunks)
        else:
            return translator.translate(text)
    except Exception as e:
        logger.error(f"Error en traducción: {e}")
        return text

# ===== Manejo de mensajes =====
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id

    if len(user_text) > 10000:
        await update.message.reply_text(f"⚠ Texto demasiado largo. Máximo 10,000 caracteres. Tu texto: {len(user_text)}")
        return

    detected_lang = detect_language(user_text)
    auto_translate = user_preferences.get(user_id, {}).get('auto_translate', False)

    if detected_lang != 'es' and detected_lang != 'unknown' and not auto_translate:
        context.user_data['pending_text'] = user_text
        keyboard = [
            [InlineKeyboardButton("✅ Sí, traducir", callback_data='translate_yes'),
             InlineKeyboardButton("❌ No, audio original", callback_data='translate_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🌍 Texto detectado en otro idioma. ¿Traducir a español?", reply_markup=reply_markup)
        return
    elif detected_lang != 'es' and detected_lang != 'unknown' and auto_translate:
        user_text = translate_text(user_text, 'es')

    await generate_and_send_audio(update.message, user_text, context, user_id)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    file_name = document.file_name.lower()
    user_id = update.effective_user.id

    if not (file_name.endswith('.pdf') or file_name.endswith('.docx')):
        await update.message.reply_text(f"❌ Solo acepto archivos PDF (.pdf) o Word (.docx). Tu archivo: {document.file_name}")
        return
    if document.file_size > 20 * 1024 * 1024:
        await update.message.reply_text(f"❌ Archivo demasiado grande. Máximo 20MB. Tu archivo: {document.file_size / (1024*1024):.1f}MB")
        return

    processing_msg = await update.message.reply_text("📄 Procesando documento...")
    try:
        file = await context.bot.get_file(document.file_id)
        file_bytes = await file.download_as_bytearray()
        file_stream = io.BytesIO(file_bytes)

        if file_name.endswith('.pdf'):
            text = extract_text_from_pdf(file_stream)
            doc_type = "PDF"
        else:
            text = extract_text_from_docx(file_stream)
            doc_type = "Word"

        if not text or len(text.strip()) < 10:
            await processing_msg.edit_text("❌ No pude extraer texto del documento. Asegúrate de que tenga texto (no solo imágenes).")
            return

        await processing_msg.edit_text(f"✅ {doc_type} procesado: {len(text)} caracteres extraídos.")
        await generate_and_send_audio(update.message, text, context, user_id)

    except Exception as e:
        logger.error(f"Error procesando documento: {e}")
        await processing_msg.edit_text(f"❌ Error al procesar el documento. Detalles: {str(e)}")

# ===== Manejo de errores =====
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.message:
        await update.message.reply_text("❌ Ocurrió un error inesperado. Intenta de nuevo.")

# ===== MAIN =====
def main():
    if not TELEGRAM_BOT_TOKEN or len(TELEGRAM_BOT_TOKEN) < 30:
        print("❌ ERROR: No has configurado el TELEGRAM_BOT_TOKEN correctamente")
        return

    print("🤖 Iniciando bot...")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.FileExtension("docx"), handle_document))
    application.add_error_handler(error_handler)

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
