import os
import io
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler, ConversationHandler
)
from docx import Document
import PyPDF2
from PyPDF2 import PdfWriter, PdfReader
from deep_translator import GoogleTranslator
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_EMAIL = "corporatebusinessunitedstates@gmail.com"
FIRMA_TEXTO = "🦅 𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸 🦅"

# Ruta de la imagen del bot (debe estar en el mismo directorio)
BOT_IMAGE_PATH = "1770404886764_image.png"

PREMIUM_USERS = {
    "Gitano": {"password": "8376", "name": "El Gitano", "email": "admin@gitano.com", "expires": datetime(2099, 12, 31)}
}

active_sessions = {}
free_usage = {}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CHOOSING_PLAN, PREMIUM_USERNAME, PREMIUM_PASSWORD, PREMIUM_BUY_DATA, FORGOT_PASSWORD = range(5)

def is_premium_active(uid):
    if uid not in active_sessions:
        return False
    username = active_sessions[uid]
    if username not in PREMIUM_USERS:
        return False
    return datetime.now() <= PREMIUM_USERS[username]["expires"]

def get_premium_info(uid):
    if uid not in active_sessions:
        return None
    username = active_sessions[uid]
    if username not in PREMIUM_USERS:
        return None
    user_data = PREMIUM_USERS[username]
    days_left = max(0, (user_data["expires"] - datetime.now()).days)
    return {"username": username, "name": user_data["name"], "days_left": days_left}

def can_use_free(uid, function_name):
    if is_premium_active(uid):
        return True
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False, "audio": False, "doc_voz": False}
    return not free_usage[uid][function_name]

def mark_free_used(uid, function_name):
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False, "audio": False, "doc_voz": False}
    free_usage[uid][function_name] = True

def all_free_used(uid):
    if uid not in free_usage:
        return False
    return all(free_usage[uid].values())

def translate_text(text, source="auto", target="es"):
    try:
        if not text or len(text.strip()) == 0:
            return ""
        translator = GoogleTranslator(source=source, target=target)
        if len(text) > 4500:
            chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
            return " ".join([translator.translate(chunk) for chunk in chunks])
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Error traducción: {e}")
        return text

def detect_language(text):
    try:
        from langdetect import detect
        lang = detect(text)
        logger.info(f"🔍 Idioma detectado: {lang} para texto: {text[:50]}...")
        return lang
    except Exception as e:
        logger.error(f"Error detectando idioma: {e}")
        return "unknown"

def tts(text, lang="es"):
    try:
        audio = io.BytesIO()
        if len(text) > 5000:
            text = text[:5000] + "..."
        logger.info(f"🔊 Generando TTS en idioma: {lang}")
        gTTS(text=text, lang=lang, slow=False).write_to_fp(audio)
        audio.seek(0)
        return audio
    except Exception as e:
        logger.error(f"Error TTS: {e}")
        return None

def transcribe_audio(audio_bytes):
    try:
        logger.info("🎤 Iniciando transcripción de audio...")
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        wav_io = io.BytesIO()
        audio.export(wav_io, format="wav")
        wav_io.seek(0)
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)
            
            try:
                text_en = recognizer.recognize_google(audio_data, language="en-US")
                logger.info(f"✅ Transcrito en inglés: {text_en}")
                return text_en, "en"
            except:
                logger.info("❌ No se pudo transcribir en inglés, intentando español...")
            
            try:
                text_es = recognizer.recognize_google(audio_data, language="es-ES")
                logger.info(f"✅ Transcrito en español: {text_es}")
                return text_es, "es"
            except:
                logger.error("❌ No se pudo transcribir en ningún idioma")
                return None, None
                
    except Exception as e:
        logger.error(f"Error transcribiendo audio: {e}")
        return None, None

def extract_text_from_pdf(file_bytes):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    except Exception as e:
        logger.error(f"Error PDF: {e}")
        return ""

def extract_text_from_docx(file_bytes):
    try:
        doc = Document(io.BytesIO(file_bytes))
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text.append(cell.text)
        return "\n".join(text)
    except Exception as e:
        logger.error(f"Error DOCX extracción: {e}")
        return ""

def translate_docx(file_bytes, source_lang="auto", target_lang="es"):
    """Traduce un documento DOCX manteniendo el formato"""
    try:
        doc = Document(io.BytesIO(file_bytes))
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                original_text = paragraph.text
                translated = translate_text(original_text, source=source_lang, target=target_lang)
                paragraph.text = translated
        
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        original_text = cell.text
                        translated = translate_text(original_text, source=source_lang, target=target_lang)
                        cell.text = translated
        
        out_stream = io.BytesIO()
        doc.save(out_stream)
        out_stream.seek(0)
        return out_stream
    except Exception as e:
        logger.error(f"Error DOCX traducción: {e}")
        return None

def translate_pdf(file_bytes, source_lang="auto", target_lang="es"):
    """Traduce un PDF y lo devuelve como PDF"""
    try:
        # Extraer texto del PDF
        text = extract_text_from_pdf(file_bytes)
        if not text:
            return None
        
        # Traducir el texto
        translated_text = translate_text(text, source=source_lang, target=target_lang)
        
        # Crear un nuevo PDF con el texto traducido
        output = io.BytesIO()
        pdf_canvas = SimpleDocTemplate(output, pagesize=letter)
        
        # Estilos
        styles = getSampleStyleSheet()
        story = []
        
        # Dividir el texto en párrafos y agregarlos
        for para in translated_text.split('\n'):
            if para.strip():
                p = Paragraph(para, styles['Normal'])
                story.append(p)
                story.append(Spacer(1, 0.2*inch))
        
        pdf_canvas.build(story)
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Error traduciendo PDF: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data.clear()
    
    message = (
        "✨ *BIENVENIDO* ✨\n\n"
        f"🎨 BOT CREADO POR:\n🦅 𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸 🦅\n\n"
        "⭐ *FUNCIONALIDADES:* ⭐\n\n"
        "📝 Texto a Voz\n"
        "🌐 Traductor Bidireccional\n"
        "📄 Traducir Documentos\n"
        "📋 Documentos a Voz\n"
        "🎤 Traducir Audio\n\n"
        "💡 *SELECCIONA TU PLAN:* 💡\n\n"
        "🆓 *FREE:* 1 uso por función\n"
        "💎 *PREMIUM:* Uso ilimitado"
    )
    
    keyboard = [
        [InlineKeyboardButton("🆓 FREE", callback_data="plan_free")],
        [InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]
    ]
    
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def plan_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    used_functions = []
    if uid in free_usage:
        if free_usage[uid].get("texto"):
            used_functions.append("📝 Texto a Voz")
        if free_usage[uid].get("documento"):
            used_functions.append("📄 Traductor Documentos")
        if free_usage[uid].get("doc_voz"):
            used_functions.append("📋 Documentos a Voz")
        if free_usage[uid].get("audio"):
            used_functions.append("🎤 Traducir Audio")
    
    if all_free_used(uid):
        message = (
            "❌ *Ya usaste todas las funciones FREE*\n\n"
            "🎯 Funciones usadas:\n"
            f"{''.join([f'• {f}' + chr(10) for f in used_functions])}\n"
            "💎 *Actualiza a PREMIUM para uso ilimitado*\n\n"
            f"{FIRMA_TEXTO}"
        )
        keyboard = [
            [InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")],
            [InlineKeyboardButton("🔙 Volver", callback_data="back_start")]
        ]
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return CHOOSING_PLAN
    
    message = "🆓 *PLAN FREE*\n\n📌 Elige una función:\n\n"
    keyboard = []
    
    if can_use_free(uid, "texto"):
        keyboard.append([InlineKeyboardButton("📝 Texto a Voz", callback_data="free_texto")])
    else:
        keyboard.append([InlineKeyboardButton("📝 Texto a Voz ❌ Usado", callback_data="used")])
    
    if can_use_free(uid, "documento"):
        keyboard.append([InlineKeyboardButton("🌐 Traductor Documentos", callback_data="free_documento")])
    else:
        keyboard.append([InlineKeyboardButton("🌐 Traductor Documentos ❌ Usado", callback_data="used")])
    
    if can_use_free(uid, "doc_voz"):
        keyboard.append([InlineKeyboardButton("📋 Documentos a Voz", callback_data="free_doc_voz")])
    else:
        keyboard.append([InlineKeyboardButton("📋 Documentos a Voz ❌ Usado", callback_data="used")])
    
    if can_use_free(uid, "audio"):
        keyboard.append([InlineKeyboardButton("🎤 Traducir Audio", callback_data="free_audio")])
    else:
        keyboard.append([InlineKeyboardButton("🎤 Traducir Audio ❌ Usado", callback_data="used")])
    
    keyboard.append([InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")])
    keyboard.append([InlineKeyboardButton("🔙 Volver", callback_data="back_start")])
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def plan_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if is_premium_active(uid):
        return await show_premium_menu(update, context)
    
    message = (
        "💎 *PLAN PREMIUM*\n\n"
        "✅ Uso ilimitado de todas las funciones\n\n"
        "🎯 *FUNCIONES:*\n"
        "📝 Texto a Voz\n"
        "🌐 Traductor Bidireccional\n"
        "📄 Traducir Documentos\n"
        "📋 Documentos a Voz\n"
        "🎤 Traducir Audio\n\n"
        f"{FIRMA_TEXTO}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔐 Iniciar Sesión", callback_data="premium_login")],
        [InlineKeyboardButton("💳 Comprar Premium", callback_data="buy_premium")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_start")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    message = (
        "💎 *COMPRAR PREMIUM*\n\n"
        "📧 Envía tus datos al correo:\n"
        f"📮 {ADMIN_EMAIL}\n\n"
        "📝 Incluye:\n"
        "• Nombre\n"
        "• Email\n"
        "• Plan deseado\n\n"
        "⏱ Te responderemos en 24h\n\n"
        f"{FIRMA_TEXTO}"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return PREMIUM_BUY_DATA

async def premium_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        "🔐 *INICIAR SESIÓN PREMIUM*\n\n📝 Escribe tu usuario:",
        parse_mode="Markdown"
    )
    return PREMIUM_USERNAME

async def premium_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    
    if username not in PREMIUM_USERS:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
        await update.message.reply_text(
            "❌ Usuario no encontrado\n\n"
            "💡 ¿Olvidaste tu contraseña?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSING_PLAN
    
    context.user_data["temp_username"] = username
    await update.message.reply_text("🔑 Escribe tu contraseña:")
    return PREMIUM_PASSWORD

async def premium_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    username = context.user_data.get("temp_username")
    uid = update.effective_user.id
    
    if username and PREMIUM_USERS.get(username, {}).get("password") == password:
        active_sessions[uid] = username
        context.user_data["is_premium"] = True
        await update.message.reply_text("✅ ¡Sesión iniciada!")
        
        fake_query = type('obj', (object,), {
            'edit_message_text': update.message.reply_text,
            'answer': lambda: None
        })()
        fake_update = type('obj', (object,), {
            'callback_query': fake_query,
            'effective_user': update.effective_user
        })()
        
        return await show_premium_menu(fake_update, context)
    else:
        keyboard = [
            [InlineKeyboardButton("🔄 Reintentar", callback_data="premium_login")],
            [InlineKeyboardButton("❓ Olvidé mi contraseña", callback_data="forgot_password")],
            [InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]
        ]
        await update.message.reply_text(
            "❌ Contraseña incorrecta",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSING_PLAN

async def forgot_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.edit_message_text(
        f"📧 Envía un email a:\n{ADMIN_EMAIL}\n\n"
        "Incluye tu usuario registrado.\n\n"
        f"{FIRMA_TEXTO}"
    )
    return FORGOT_PASSWORD

async def process_forgot_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
    await update.message.reply_text(
        "✅ Solicitud recibida.\n"
        f"Revisa {ADMIN_EMAIL} en 24h.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_PLAN

async def show_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    info = get_premium_info(uid)
    if not info:
        return await plan_premium(update, context)
    
    message = (
        f"💎 *MENÚ PREMIUM*\n\n"
        f"👤 Usuario: {info['name']}\n"
        f"⏰ Días restantes: {info['days_left']}\n\n"
        "🎯 *Elige una función:*"
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 Texto a Voz", callback_data="premium_texto")],
        [InlineKeyboardButton("🌐 Traductor Documentos", callback_data="premium_documento")],
        [InlineKeyboardButton("📋 Documentos a Voz", callback_data="premium_doc_voz")],
        [InlineKeyboardButton("🎤 Traducir Audio", callback_data="premium_audio")],
        [InlineKeyboardButton("🚪 Cerrar Sesión", callback_data="premium_logout")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def free_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not can_use_free(uid, "texto"):
        await query.answer("❌ Ya usaste esta función", show_alert=True)
        return CHOOSING_PLAN
    
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = False
    
    # Enviar imagen guía si existe
    try:
        if os.path.exists(BOT_IMAGE_PATH):
            with open(BOT_IMAGE_PATH, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=(
                        "📝 *TEXTO A VOZ*\n\n"
                        "📌 Guía de uso:\n"
                        "1️⃣ Envía un texto\n"
                        "2️⃣ Elige si quieres traducción\n"
                        "3️⃣ Recibe tu audio\n\n"
                        f"{FIRMA_TEXTO}"
                    ),
                    parse_mode="Markdown"
                )
        else:
            await query.message.reply_text(
                "📝 *TEXTO A VOZ*\n\n"
                "✍️ Envía el texto que quieres convertir a voz\n\n"
                f"{FIRMA_TEXTO}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error enviando imagen: {e}")
        await query.message.reply_text(
            "📝 *TEXTO A VOZ*\n\n"
            "✍️ Envía el texto que quieres convertir a voz\n\n"
            f"{FIRMA_TEXTO}",
            parse_mode="Markdown"
        )
    
    await query.answer()
    return CHOOSING_PLAN

async def premium_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not is_premium_active(uid):
        await query.answer("❌ Sesión expirada", show_alert=True)
        return await plan_premium(update, context)
    
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = True
    
    # Enviar imagen guía si existe
    try:
        if os.path.exists(BOT_IMAGE_PATH):
            with open(BOT_IMAGE_PATH, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=(
                        "📝 *TEXTO A VOZ*\n\n"
                        "📌 Guía de uso:\n"
                        "1️⃣ Envía un texto\n"
                        "2️⃣ Elige si quieres traducción\n"
                        "3️⃣ Recibe tu audio\n\n"
                        f"{FIRMA_TEXTO}"
                    ),
                    parse_mode="Markdown"
                )
        else:
            await query.message.reply_text(
                "📝 *TEXTO A VOZ*\n\n"
                "✍️ Envía el texto que quieres convertir a voz\n\n"
                f"{FIRMA_TEXTO}",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Error enviando imagen: {e}")
        await query.message.reply_text(
            "📝 *TEXTO A VOZ*\n\n"
            "✍️ Envía el texto que quieres convertir a voz\n\n"
            f"{FIRMA_TEXTO}",
            parse_mode="Markdown"
        )
    
    await query.answer()
    return CHOOSING_PLAN

async def free_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not can_use_free(uid, "documento"):
        await query.answer("❌ Ya usaste esta función", show_alert=True)
        return CHOOSING_PLAN
    
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "translate"
    context.user_data["is_premium"] = False
    
    await query.message.reply_text(
        "📄 *TRADUCTOR DE DOCUMENTOS*\n\n"
        "📎 Envía un documento (PDF o DOCX)\n\n"
        "🌐 Se traducirá automáticamente:\n"
        "• 🇪🇸 Español → 🇺🇸 Inglés\n"
        "• 🇺🇸 Inglés → 🇪🇸 Español\n\n"
        "📋 El documento se entregará en el mismo formato\n\n"
        f"{FIRMA_TEXTO}",
        parse_mode="Markdown"
    )
    await query.answer()
    return CHOOSING_PLAN

async def premium_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not is_premium_active(uid):
        await query.answer("❌ Sesión expirada", show_alert=True)
        return await plan_premium(update, context)
    
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "translate"
    context.user_data["is_premium"] = True
    
    await query.message.reply_text(
        "📄 *TRADUCTOR DE DOCUMENTOS*\n\n"
        "📎 Envía un documento (PDF o DOCX)\n\n"
        "🌐 Se traducirá automáticamente:\n"
        "• 🇪🇸 Español → 🇺🇸 Inglés\n"
        "• 🇺🇸 Inglés → 🇪🇸 Español\n\n"
        "📋 El documento se entregará en el mismo formato\n\n"
        f"{FIRMA_TEXTO}",
        parse_mode="Markdown"
    )
    await query.answer()
    return CHOOSING_PLAN

async def free_doc_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not can_use_free(uid, "doc_voz"):
        await query.answer("❌ Ya usaste esta función", show_alert=True)
        return CHOOSING_PLAN
    
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "voice"
    context.user_data["is_premium"] = False
    
    await query.message.reply_text(
        "📋 *DOCUMENTOS A VOZ*\n\n"
        "📎 Envía un documento (PDF o DOCX)\n\n"
        "🔊 Recibirás el audio del contenido traducido\n\n"
        f"{FIRMA_TEXTO}",
        parse_mode="Markdown"
    )
    await query.answer()
    return CHOOSING_PLAN

async def premium_doc_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not is_premium_active(uid):
        await query.answer("❌ Sesión expirada", show_alert=True)
        return await plan_premium(update, context)
    
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "voice"
    context.user_data["is_premium"] = True
    
    await query.message.reply_text(
        "📋 *DOCUMENTOS A VOZ*\n\n"
        "📎 Envía un documento (PDF o DOCX)\n\n"
        "🔊 Recibirás el audio del contenido traducido\n\n"
        f"{FIRMA_TEXTO}",
        parse_mode="Markdown"
    )
    await query.answer()
    return CHOOSING_PLAN

async def free_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not can_use_free(uid, "audio"):
        await query.answer("❌ Ya usaste esta función", show_alert=True)
        return CHOOSING_PLAN
    
    context.user_data["waiting_audio"] = True
    context.user_data["is_premium"] = False
    
    await query.message.reply_text(
        "🎤 *TRADUCIR AUDIO*\n\n"
        "🎙 Envía un audio o nota de voz\n\n"
        "🌐 Se transcribirá y traducirá:\n"
        "• 🇪🇸 Español → 🇺🇸 Inglés\n"
        "• 🇺🇸 Inglés → 🇪🇸 Español\n\n"
        f"{FIRMA_TEXTO}",
        parse_mode="Markdown"
    )
    await query.answer()
    return CHOOSING_PLAN

async def premium_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    
    if not is_premium_active(uid):
        await query.answer("❌ Sesión expirada", show_alert=True)
        return await plan_premium(update, context)
    
    context.user_data["waiting_audio"] = True
    context.user_data["is_premium"] = True
    
    await query.message.reply_text(
        "🎤 *TRADUCIR AUDIO*\n\n"
        "🎙 Envía un audio o nota de voz\n\n"
        "🌐 Se transcribirá y traducirá:\n"
        "• 🇪🇸 Español → 🇺🇸 Inglés\n"
        "• 🇺🇸 Inglés → 🇪🇸 Español\n\n"
        f"{FIRMA_TEXTO}",
        parse_mode="Markdown"
    )
    await query.answer()
    return CHOOSING_PLAN

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    
    # Si está esperando respuesta de traducción
    if context.user_data.get("waiting_translate_response"):
        response = update.message.text.strip().upper()
        
        if response not in ["SI", "SÍ", "NO"]:
            keyboard = [
                [InlineKeyboardButton("✅ SI", callback_data="translate_yes")],
                [InlineKeyboardButton("❌ NO", callback_data="translate_no")]
            ]
            await update.message.reply_text(
                "❓ Por favor, responde SI o NO\n\n"
                "¿Quieres que el audio sea traducido?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return CHOOSING_PLAN
        
        text_to_process = context.user_data.get("text_to_process", "")
        lang = detect_language(text_to_process)
        
        processing_msg = await update.message.reply_text("⏳ Generando audio...")
        
        if response in ["SI", "SÍ"]:
            # Usuario quiere traducción
            if lang == "es":
                target_lang = "en"
                audio_lang = "en"
                lang_display = "🇪🇸→🇺🇸"
                translated_text = translate_text(text_to_process, source="es", target="en")
            else:
                target_lang = "es"
                audio_lang = "es"
                lang_display = "🇺🇸→🇪🇸"
                translated_text = translate_text(text_to_process, source="en", target="es")
            
            audio = tts(translated_text, audio_lang)
            caption = f"{lang_display} Audio traducido\n\n{FIRMA_TEXTO}"
        else:
            # Usuario NO quiere traducción - audio en idioma original
            if lang == "es":
                audio_lang = "es"
            else:
                audio_lang = "en"
            
            audio = tts(text_to_process, audio_lang)
            caption = f"🔊 Audio en idioma original\n\n{FIRMA_TEXTO}"
        
        if audio:
            await update.message.reply_voice(audio, caption=caption)
        else:
            await update.message.reply_text("❌ Error al generar audio.")
            await processing_msg.delete()
            return CHOOSING_PLAN
        
        if not context.user_data.get("is_premium", False):
            mark_free_used(uid, "texto")
        
        if not context.user_data.get("is_premium", False) and all_free_used(uid):
            keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
            await update.message.reply_text(f"✅ Ya usaste FREE\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["waiting_text"] = False
            context.user_data["waiting_translate_response"] = False
        else:
            back = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data=back)]]
            await update.message.reply_text(f"✅ Listo. Envía otro texto o vuelve.\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
        
        context.user_data["waiting_translate_response"] = False
        context.user_data["text_to_process"] = ""
        await processing_msg.delete()
        return CHOOSING_PLAN
    
    # Si está esperando texto para convertir a voz
    if not context.user_data.get("waiting_text", False):
        return CHOOSING_PLAN
    
    text = update.message.text.strip()
    
    if not text:
        await update.message.reply_text("❌ Texto vacío. Envía un texto válido.")
        return CHOOSING_PLAN
    
    # Guardar el texto y preguntar si quiere traducción
    context.user_data["text_to_process"] = text
    context.user_data["waiting_translate_response"] = True
    
    keyboard = [
        [InlineKeyboardButton("✅ SI", callback_data="translate_yes")],
        [InlineKeyboardButton("❌ NO", callback_data="translate_no")]
    ]
    
    await update.message.reply_text(
        "🌐 ¿Quieres que el audio sea traducido?\n\n"
        "• SI: El audio se traducirá (ES↔EN)\n"
        "• NO: El audio será en el idioma original",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return CHOOSING_PLAN

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.user_data.get("waiting_document", False):
        return
    
    try:
        processing_msg = await update.message.reply_text("⏳ Procesando documento...")
        
        doc = update.message.document
        file = await context.bot.get_file(doc.file_id)
        data = await file.download_as_bytearray()
        
        document_mode = context.user_data.get("document_mode", "translate")
        is_docx = doc.file_name.endswith(".docx")
        is_pdf = doc.file_name.endswith(".pdf")
        
        if not (is_docx or is_pdf):
            await update.message.reply_text("❌ Solo se permiten archivos PDF o DOCX")
            await processing_msg.delete()
            return
        
        # Extraer texto según tipo de documento
        if is_docx:
            text = extract_text_from_docx(data)
        else:
            text = extract_text_from_pdf(data)
        
        if not text:
            await update.message.reply_text("❌ No se pudo extraer texto del documento")
            await processing_msg.delete()
            return
        
        lang = detect_language(text)
        
        if lang == "es":
            target_lang = "en"
            lang_display = "🇪🇸→🇺🇸"
            audio_lang = "en"
        else:
            target_lang = "es"
            lang_display = "🇺🇸→🇪🇸"
            audio_lang = "es"
        
        if document_mode == "translate":
            # Modo traducción - mantener formato original
            if is_docx:
                translated_file = translate_docx(data, source_lang=lang, target_lang=target_lang)
                extension = ".docx"
            else:
                translated_file = translate_pdf(data, source_lang=lang, target_lang=target_lang)
                extension = ".pdf"
            
            if translated_file:
                filename = f"traducido_{lang_display.replace('🇪🇸', 'ES').replace('🇺🇸', 'EN').replace('→', '_')}_{doc.file_name.replace('.pdf', extension).replace('.docx', extension)}"
                await update.message.reply_document(
                    document=translated_file,
                    filename=filename,
                    caption=f"{lang_display} Documento traducido\n\n{FIRMA_TEXTO}"
                )
            else:
                await update.message.reply_text("❌ Error al traducir.")
                await processing_msg.delete()
                return
            
            if not context.user_data.get("is_premium", False):
                mark_free_used(uid, "documento")
        else:
            # Modo documento a voz
            translated_text = translate_text(text, source=lang, target=target_lang)
            audio = tts(translated_text, audio_lang)
            
            if audio:
                await update.message.reply_voice(audio, caption=f"{lang_display} Documento a voz\n\n{FIRMA_TEXTO}")
            else:
                await update.message.reply_text("❌ Error al generar audio.")
                await processing_msg.delete()
                return
            
            if not context.user_data.get("is_premium", False):
                mark_free_used(uid, "doc_voz")
        
        if not context.user_data.get("is_premium", False) and all_free_used(uid):
            keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
            await update.message.reply_text(f"✅ Ya usaste FREE\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["waiting_document"] = False
        else:
            back = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data=back)]]
            await update.message.reply_text(f"✅ Listo. Envía otro documento o vuelve.\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
        
        await processing_msg.delete()
    except Exception as e:
        logger.error(f"❌ Error documento: {e}")
        await update.message.reply_text("❌ Error procesando documento.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.user_data.get("waiting_audio", False):
        return
    
    try:
        processing_msg = await update.message.reply_text("⏳ Transcribiendo audio...")
        
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        audio_bytes = await file.download_as_bytearray()
        
        text, detected_lang = transcribe_audio(audio_bytes)
        
        if not text:
            await update.message.reply_text(
                "❌ No se pudo transcribir el audio.\n\n"
                "Asegúrate de hablar claramente.",
                parse_mode="Markdown"
            )
            await processing_msg.delete()
            back = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data=back)]]
            await update.message.reply_text(FIRMA_TEXTO, reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        if detected_lang == "es":
            target_lang = "en"
            lang_display = "🇪🇸→🇺🇸"
            audio_lang = "en"
        else:
            target_lang = "es"
            lang_display = "🇺🇸→🇪🇸"
            audio_lang = "es"
        
        translated_text = translate_text(text, source=detected_lang, target=target_lang)
        
        await update.message.reply_text(
            f"📝 *Transcripción:*\n{text}\n\n"
            f"{lang_display} *Traducción:*\n{translated_text}",
            parse_mode="Markdown"
        )
        
        audio_translated = tts(translated_text, audio_lang)
        if audio_translated:
            await update.message.reply_voice(
                audio_translated,
                caption=f"{lang_display} Audio traducido\n\n{FIRMA_TEXTO}"
            )
        
        if not context.user_data.get("is_premium", False):
            mark_free_used(uid, "audio")
        
        if not context.user_data.get("is_premium", False) and all_free_used(uid):
            keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
            await update.message.reply_text(f"✅ Ya usaste FREE\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["waiting_audio"] = False
        else:
            back = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data=back)]]
            await update.message.reply_text(f"✅ Listo. Envía otro audio o vuelve.\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
        
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"❌ Error audio: {e}")
        await update.message.reply_text("❌ Error procesando audio.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # Manejar respuestas de traducción SI/NO
    if data == "translate_yes":
        # Simular que el usuario escribió "SI"
        fake_message = type('obj', (object,), {
            'text': 'SI',
            'reply_text': query.message.reply_text,
            'reply_voice': query.message.reply_voice
        })()
        fake_update = type('obj', (object,), {
            'message': fake_message,
            'effective_user': update.effective_user,
            'callback_query': query
        })()
        return await handle_text(fake_update, context)
    
    elif data == "translate_no":
        # Simular que el usuario escribió "NO"
        fake_message = type('obj', (object,), {
            'text': 'NO',
            'reply_text': query.message.reply_text,
            'reply_voice': query.message.reply_voice
        })()
        fake_update = type('obj', (object,), {
            'message': fake_message,
            'effective_user': update.effective_user,
            'callback_query': query
        })()
        return await handle_text(fake_update, context)
    
    if data == "back_start":
        context.user_data.clear()
        return await start(update, context)
    elif data == "plan_free":
        return await plan_free(update, context)
    elif data == "plan_premium":
        return await plan_premium(update, context)
    elif data == "buy_premium":
        return await buy_premium(update, context)
    elif data == "premium_login":
        return await premium_login(update, context)
    elif data == "forgot_password":
        return await forgot_password(update, context)
    elif data == "free_texto":
        return await free_texto(update, context)
    elif data == "free_documento":
        return await free_documento(update, context)
    elif data == "free_doc_voz":
        return await free_doc_voz(update, context)
    elif data == "free_audio":
        return await free_audio(update, context)
    elif data == "premium_menu":
        return await show_premium_menu(update, context)
    elif data == "premium_texto":
        return await premium_texto(update, context)
    elif data == "premium_documento":
        return await premium_documento(update, context)
    elif data == "premium_doc_voz":
        return await premium_doc_voz(update, context)
    elif data == "premium_audio":
        return await premium_audio(update, context)
    elif data == "premium_logout":
        uid = update.effective_user.id
        if uid in active_sessions:
            del active_sessions[uid]
        await query.edit_message_text("✅ Sesión cerrada.", parse_mode="Markdown")
        return await start(update, context)
    
    return CHOOSING_PLAN

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ Error. Usa /start")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TOKEN NO CONFIGURADO")
        return
    
    logger.info("🚀 Iniciando bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_PLAN: [
                CallbackQueryHandler(button_callback),
                MessageHandler(filters.VOICE, handle_voice),
                MessageHandler(filters.Document.ALL, handle_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)
            ],
            PREMIUM_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_username)],
            PREMIUM_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_password)],
            PREMIUM_BUY_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_buy_data)],
            FORGOT_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_forgot_password)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    
    app.add_handler(conv_handler)
    app.add_error_handler(error_handler)
    
    logger.info("✅ Bot listo")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
