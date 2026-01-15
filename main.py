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
import tempfile

# Configuración de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====== CONFIGURACIÓN - SOLO PON TU TOKEN DE TELEGRAM ======
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Configuración de voces disponibles en gTTS
AVAILABLE_ACCENTS = {
    'es-es': '🇪🇸 Español de España',
    'es-us': '🇲🇽 Español Latino (México)',
    'es-mx': '🇲🇽 Español de México',
    'es-ar': '🇦🇷 Español de Argentina',
    'es-co': '🇨🇴 Español de Colombia',
    'es-cl': '🇨🇱 Español de Chile',
    'es': '🌎 Español General'
}

# Velocidades disponibles
SPEED_OPTIONS = {
    'slow': {'speed': True, 'name': '🐌 Lento'},
    'normal': {'speed': False, 'name': '✅ Normal'}
}

# ============================================================

# Almacenamiento de preferencias de usuario
user_preferences = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start"""
    await update.message.reply_text(
        "¡Hola! 👋 Soy tu bot de Text-to-Speech 100% GRATUITO\n\n"
        "🎯 *Funcionalidades:*\n"
        "📝 Convierte texto a voz (GRATIS, sin límites)\n"
        "📄 Lee archivos PDF y Word\n"
        "🌎 Traduce automáticamente a español\n"
        "🎙️ Múltiples acentos latinos disponibles\n"
        "🎚️ Velocidad ajustable\n\n"
        "📌 *Cómo usarme:*\n"
        "• Envíame texto directamente\n"
        "• Envíame un archivo PDF o Word (.docx)\n"
        "• Si el documento está en otro idioma, te preguntaré si quieres traducirlo\n\n"
        "⚙️ *Comandos:*\n"
        "/start - Ver este mensaje\n"
        "/help - Ayuda detallada\n"
        "/config - Traducción automática\n"
        "/accent - Cambiar acento (España, México, etc.)\n"
        "/speed - Ajustar velocidad\n\n"
        "💯 *100% GRATUITO - Sin límites ni API Keys*\n\n"
        "¡Pruébame ahora! 😊",
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    await update.message.reply_text(
        "ℹ️ *Guía Completa del Bot*\n\n"
        "📝 *TEXTO:*\n"
        "Envía cualquier texto y lo convertiré a audio.\n"
        "Respeto puntuación, comas, puntos y acentos.\n\n"
        "📄 *ARCHIVOS PDF:*\n"
        "Envía un PDF y extraeré todo el texto.\n"
        "Si es muy largo, te lo dividiré en partes.\n\n"
        "📋 *ARCHIVOS WORD (.docx):*\n"
        "Envía un documento Word y lo procesaré.\n"
        "Funciona con formatos .docx modernos.\n\n"
        "🌍 *TRADUCCIÓN:*\n"
        "Detecto automáticamente el idioma.\n"
        "Si no está en español, te pregunto si quieres traducirlo.\n"
        "Configura traducción automática con /config\n\n"
        "🎙️ *PERSONALIZACIÓN:*\n"
        "/accent - Cambiar acento español\n"
        "/speed - Ajustar velocidad del audio\n\n"
        "⚠️ *LÍMITES:*\n"
        "• Texto: máximo 5000 caracteres por mensaje\n"
        "• Archivos: se procesarán los primeros 10,000 caracteres\n"
        "• 100% GRATUITO sin límites de uso\n\n"
        "💡 *Ventajas:*\n"
        "✅ No requiere API Key\n"
        "✅ Sin límites de caracteres mensuales\n"
        "✅ Múltiples acentos latinos\n"
        "✅ Completamente gratis",
        parse_mode='Markdown'
    )

async def accent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /accent para cambiar el acento"""
    keyboard = [
        [InlineKeyboardButton(AVAILABLE_ACCENTS['es-us'], callback_data='accent_es-us')],
        [InlineKeyboardButton(AVAILABLE_ACCENTS['es-mx'], callback_data='accent_es-mx')],
        [InlineKeyboardButton(AVAILABLE_ACCENTS['es-ar'], callback_data='accent_es-ar')],
        [InlineKeyboardButton(AVAILABLE_ACCENTS['es-co'], callback_data='accent_es-co')],
        [InlineKeyboardButton(AVAILABLE_ACCENTS['es-es'], callback_data='accent_es-es')],
        [InlineKeyboardButton(AVAILABLE_ACCENTS['es'], callback_data='accent_es')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_id = update.effective_user.id
    current_accent = user_preferences.get(user_id, {}).get('accent', 'es-us')
    
    await update.message.reply_text(
        f"🌎 *Selecciona un acento español*\n\n"
        f"Acento actual: {AVAILABLE_ACCENTS.get(current_accent, current_accent)}\n\n"
        f"Elige tu acento favorito:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def speed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /speed para ajustar velocidad"""
    keyboard = [
        [InlineKeyboardButton("🐌 Lento", callback_data='speed_slow')],
        [InlineKeyboardButton("✅ Normal", callback_data='speed_normal')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user_id = update.effective_user.id
    current_speed = user_preferences.get(user_id, {}).get('speed', 'normal')
    speed_name = SPEED_OPTIONS[current_speed]['name']
    
    await update.message.reply_text(
        f"🎚️ *Ajustar velocidad del audio*\n\n"
        f"Velocidad actual: {speed_name}\n\n"
        f"Elige la velocidad que prefieras:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /config para configurar preferencias"""
    user_id = update.effective_user.id
    current_auto = user_preferences.get(user_id, {}).get('auto_translate', False)
    
    keyboard = [
        [
            InlineKeyboardButton("✅ Traducción Automática ON" if current_auto else "⬜ Traducción Automática OFF", 
                               callback_data='toggle_auto_translate')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ *Configuración*\n\n"
        f"Traducción automática: {'✅ Activada' if current_auto else '❌ Desactivada'}\n\n"
        "Cuando está activada, traduciré automáticamente cualquier texto "
        "en otro idioma sin preguntarte.",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones de configuración"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if user_id not in user_preferences:
        user_preferences[user_id] = {}
    
    if query.data == 'toggle_auto_translate':
        current = user_preferences[user_id].get('auto_translate', False)
        user_preferences[user_id]['auto_translate'] = not current
        new_value = user_preferences[user_id]['auto_translate']
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Traducción Automática ON" if new_value else "⬜ Traducción Automática OFF", 
                                   callback_data='toggle_auto_translate')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "⚙️ *Configuración*\n\n"
            f"Traducción automática: {'✅ Activada' if new_value else '❌ Desactivada'}\n\n"
            "Cuando está activada, traduciré automáticamente cualquier texto "
            "en otro idioma sin preguntarte.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    elif query.data.startswith('accent_'):
        accent = query.data.replace('accent_', '')
        user_preferences[user_id]['accent'] = accent
        accent_name = AVAILABLE_ACCENTS.get(accent, accent)
        await query.edit_message_text(
            f"✅ Acento cambiado a: {accent_name}\n\n"
            f"Envía un texto para probar el nuevo acento.",
            parse_mode='Markdown'
        )
    
    elif query.data.startswith('speed_'):
        speed = query.data.replace('speed_', '')
        user_preferences[user_id]['speed'] = speed
        speed_name = SPEED_OPTIONS[speed]['name']
        await query.edit_message_text(
            f"✅ Velocidad ajustada a: {speed_name}\n\n"
            f"Envía un texto para probar la nueva velocidad.",
            parse_mode='Markdown'
        )
    
    elif query.data.startswith('translate_'):
        action = query.data.split('_')[1]
        
        if action == 'yes':
            original_text = context.user_data.get('pending_text', '')
            if original_text:
                await query.edit_message_text("🔄 Traduciendo a español...")
                translated = translate_text(original_text, 'es')
                await generate_and_send_audio(query.message, translated, context, user_id)
            else:
                await query.edit_message_text("❌ Error: No se encontró el texto a traducir.")
        else:
            original_text = context.user_data.get('pending_text', '')
            if original_text:
                await query.edit_message_text("✅ Generando audio en idioma original...")
                await generate_and_send_audio(query.message, original_text, context, user_id)

def detect_language(text: str) -> str:
    """Detecta el idioma del texto"""
    try:
        return detect(text)
    except:
        return 'unknown'

def translate_text(text: str, target_lang: str = 'es') -> str:
    """Traduce texto usando Google Translator"""
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

def extract_text_from_pdf(pdf_file) -> str:
    """Extrae texto de un archivo PDF"""
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
    """Extrae texto de un archivo Word"""
    try:
        doc = Document(docx_file)
        text = ""
        
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        
        return text.strip()
    except Exception as e:
        logger.error(f"Error extrayendo texto de Word: {e}")
        raise

def text_to_speech_gtts(text: str, user_id: int) -> bytes:
    """Convierte texto a audio usando gTTS (Google Text-to-Speech)"""
    
    # Obtener preferencias del usuario
    accent = user_preferences.get(user_id, {}).get('accent', 'es-us')
    speed_setting = user_preferences.get(user_id, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed_setting]['speed']
    
    # Crear el objeto gTTS
    tts = gTTS(text=text, lang=accent, slow=slow)
    
    # Guardar en memoria
    audio_fp = io.BytesIO()
    tts.write_to_fp(audio_fp)
    audio_fp.seek(0)
    
    return audio_fp.read()

async def generate_and_send_audio(message, text: str, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Genera y envía el audio"""
    if len(text) > 10000:
        text = text[:10000]
        await message.reply_text(
            "⚠️ El texto es muy largo. Procesaré los primeros 10,000 caracteres."
        )
    
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
                    caption=f"🔊 Parte {idx}/{min(len(chunks), 3)} ({len(chunk)} caracteres)"
                )
            
            if len(chunks) > 3:
                await message.reply_text(
                    f"ℹ️ El documento tiene más partes. Se procesaron las primeras 3 ({max_chunk_size * 3} caracteres)."
                )
        else:
            audio_data = text_to_speech_gtts(text, user_id)
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.mp3"
            
            await message.reply_voice(
                voice=audio_file,
                caption=f"🔊 Audio generado ({len(text)} caracteres)"
            )
        
        await processing_msg.delete()
        logger.info(f"Audio generado exitosamente para usuario {user_id}")
        
    except Exception as e:
        logger.error(f"Error al generar audio: {e}")
        await processing_msg.edit_text(
            "❌ Error al generar el audio.\n\n"
            f"Detalles: {str(e)}"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los mensajes de texto"""
    
    user_text = update.message.text
    user_id = update.effective_user.id
    
    if len(user_text) > 10000:
        await update.message.reply_text(
            "⚠️ El texto es demasiado largo. Máximo 10,000 caracteres.\n"
            f"Tu texto tiene {len(user_text)} caracteres."
        )
        return
    
    detected_lang = detect_language(user_text)
    auto_translate = user_preferences.get(user_id, {}).get('auto_translate', False)
    
    if detected_lang != 'es' and detected_lang != 'unknown' and not auto_translate:
        context.user_data['pending_text'] = user_text
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Sí, traducir", callback_data='translate_yes'),
                InlineKeyboardButton("❌ No, audio original", callback_data='translate_no')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        lang_names = {
            'en': 'inglés', 'fr': 'francés', 'de': 'alemán', 'it': 'italiano',
            'pt': 'portugués', 'ru': 'ruso', 'zh-cn': 'chino', 'ja': 'japonés',
            'ko': 'coreano', 'ar': 'árabe'
        }
        lang_name = lang_names.get(detected_lang, detected_lang)
        
        await update.message.reply_text(
            f"🌍 Detecté que el texto está en *{lang_name}*.\n\n"
            "¿Quieres que lo traduzca a español antes de generar el audio?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        return
    
    if detected_lang != 'es' and detected_lang != 'unknown' and auto_translate:
        await update.message.reply_text("🔄 Traduciendo automáticamente a español...")
        user_text = translate_text(user_text, 'es')
    
    await generate_and_send_audio(update.message, user_text, context, user_id)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja archivos PDF y Word"""
    
    document = update.message.document
    file_name = document.file_name.lower()
    user_id = update.effective_user.id
    
    if not (file_name.endswith('.pdf') or file_name.endswith('.docx')):
        await update.message.reply_text(
            "❌ Solo acepto archivos PDF (.pdf) o Word (.docx).\n"
            f"Tu archivo: {document.file_name}"
        )
        return
    
    if document.file_size > 20 * 1024 * 1024:
        await update.message.reply_text(
            "❌ El archivo es demasiado grande. Máximo 20MB.\n"
            f"Tu archivo: {document.file_size / (1024*1024):.1f}MB"
        )
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
            await processing_msg.edit_text(
                "❌ No pude extraer texto del documento.\n"
                "Asegúrate de que el archivo contenga texto (no solo imágenes)."
            )
            return
        
        await processing_msg.edit_text(
            f"✅ {doc_type} procesado: {len(text)} caracteres extraídos."
        )
        
        detected_lang = detect_language(text[:1000])
        auto_translate = user_preferences.get(user_id, {}).get('auto_translate', False)
        
        if detected_lang != 'es' and detected_lang != 'unknown':
            if auto_translate:
                await update.message.reply_text("🔄 Traduciendo documento a español...")
                text = translate_text(text, 'es')
            else:
                context.user_data['pending_text'] = text
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Sí, traducir", callback_data='translate_yes'),
                        InlineKeyboardButton("❌ No, audio original", callback_data='translate_no')
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                lang_names = {
                    'en': 'inglés', 'fr': 'francés', 'de': 'alemán', 'it': 'italiano',
                    'pt': 'portugués', 'ru': 'ruso'
                }
                lang_name = lang_names.get(detected_lang, detected_lang)
                
                await update.message.reply_text(
                    f"🌍 El documento parece estar en *{lang_name}*.\n\n"
                    "¿Quieres que lo traduzca a español?",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                return
        
        await generate_and_send_audio(update.message, text, context, user_id)
        
    except Exception as e:
        logger.error(f"Error procesando documento: {e}")
        await processing_msg.edit_text(
            f"❌ Error al procesar el documento.\n\n"
            f"Detalles: {str(e)}"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores"""
    logger.error(f"Error: {context.error}")
    
    if update and update.message:
        await update.message.reply_text(
            "❌ Ocurrió un error inesperado.\n"
            "Por favor, intenta de nuevo."
        )

def main():
    """Función principal"""
    
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "TU_TOKEN_DE_TELEGRAM_AQUI" or len(TELEGRAM_BOT_TOKEN) < 30:
        print("❌ ERROR: No has configurado el TELEGRAM_BOT_TOKEN")
        print("Edita el archivo y pon tu token en la línea 17")
        return
    
    print("🤖 Iniciando bot con gTTS (100% GRATUITO)...")
    print("   📝 Text-to-Speech sin límites")
    print("   📄 Lectura de PDF y Word")
    print("   🌍 Traducción automática")
    print("   🎙️ Múltiples acentos latinos")
    print("   💯 Sin API Keys ni tarjetas")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("config", config_command))
    application.add_handler(CommandHandler("accent", accent_command))
    application.add_handler(CommandHandler("speed", speed_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.Document.PDF | filters.Document.FileExtension("docx"), handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    application.add_error_handler(error_handler)
    
    print("\n✅ Bot iniciado correctamente")
    print("📱 Características:")
    print("   • 100% GRATUITO sin límites")
    print("   • Sin API Key necesaria")
    print("   • Múltiples acentos latinos")
    print("   • /accent para cambiar acento")
    print("   • /speed para ajustar velocidad")
    print("\n🛑 Presiona Ctrl+C para detener el bot\n")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
