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
from deep_translator import GoogleTranslator
from gtts import gTTS
import speech_recognition as sr
from pydub import AudioSegment

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_EMAIL = "corporatebusinessunitedstates@gmail.com"
FIRMA_TEXTO = "🦅 𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸 🦅"

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

def translate_pdf_to_docx(file_bytes, source_lang="auto", target_lang="es"):
    try:
        text = extract_text_from_pdf(file_bytes)
        if not text:
            return None
        translated_text = translate_text(text, source=source_lang, target=target_lang)
        doc = Document()
        doc.add_paragraph(translated_text)
        out_stream = io.BytesIO()
        doc.save(out_stream)
        out_stream.seek(0)
        return out_stream
    except Exception as e:
        logger.error(f"Error PDF to DOCX: {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data.clear()
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False, "audio": False, "doc_voz": False}
    
    keyboard = [[InlineKeyboardButton("🆓 FREE", callback_data="plan_free"), InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ 𝗕𝗜𝗘𝗡𝗩𝗘𝗡𝗜𝗗𝗢 ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *BOT CREADO POR:*\n"
        "🦅 *𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸* 🦅\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌟 *FUNCIONALIDADES:* 🌟\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 Texto a Voz\n"
        "🌐 Traductor Bidireccional\n"
        "📄 Traducir Documentos\n"
        "🎙️ Documentos a Voz\n"
        "🔊 Traducir Audio\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *SELECCIONA TU PLAN:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🆓 *FREE:* 1 uso por función\n"
        "💎 *PREMIUM:* Uso ilimitado\n\n"
        "👇 *Elige una opción:* 👇"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def plan_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    
    if all_free_used(uid):
        keyboard = [[InlineKeyboardButton("💎 COMPRAR PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n🎊 *¡ULALA!* 🎊\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Ya utilizaste tu prueba FREE*\n\nCompra PREMIUM.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n💎 *PREMIUM - $27 USD/30 días*\n━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
        return CHOOSING_PLAN
    
    texto_status = "✅" if not free_usage[uid]["texto"] else "❌"
    doc_status = "✅" if not free_usage[uid]["documento"] else "❌"
    doc_voz_status = "✅" if not free_usage[uid]["doc_voz"] else "❌"
    audio_status = "✅" if not free_usage[uid]["audio"] else "❌"
    
    keyboard = [
        [InlineKeyboardButton(f"{texto_status} 📝 Texto a Voz", callback_data="free_texto")],
        [InlineKeyboardButton(f"{doc_status} 📄 Traducir Documentos", callback_data="free_documento")],
        [InlineKeyboardButton(f"{doc_voz_status} 🎙️ Documentos a Voz", callback_data="free_doc_voz")],
        [InlineKeyboardButton(f"{audio_status} 🔊 Traducir Audio", callback_data="free_audio")],
        [InlineKeyboardButton("💎 Actualizar a PREMIUM", callback_data="plan_premium")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_start")]
    ]
    
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n🆓 *MODO FREE* 🆓\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Tienes *1 uso* por función:\n\n"
        f"{texto_status} *Texto a Voz*\n{doc_status} *Traducir Documentos*\n{doc_voz_status} *Documentos a Voz*\n{audio_status} *Traducir Audio*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n👇 *Selecciona:* 👇\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def plan_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    
    if is_premium_active(uid):
        return await show_premium_menu(update, context)
    
    keyboard = [
        [InlineKeyboardButton("🔑 INGRESAR", callback_data="premium_login")],
        [InlineKeyboardButton("💰 COMPRAR PREMIUM", callback_data="buy_premium")],
        [InlineKeyboardButton("🔐 Olvidé mi Contraseña", callback_data="forgot_password")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_start")]
    ]
    
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n💎 *PREMIUM* 💎\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ *BENEFICIOS:*\n"
        "✅ Uso ilimitado\n✅ Traducción bidireccional\n✅ Sin restricciones\n\n"
        "💵 *$27 USD / 30 días*\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("🔐 *LOGIN PREMIUM*\n\nEnvía tu *USUARIO*:", parse_mode="Markdown")
    return PREMIUM_USERNAME

async def premium_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    context.user_data["premium_username_attempt"] = username
    
    if username not in PREMIUM_USERS:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
        await update.message.reply_text(
            f"❌ Usuario '{username}' no existe.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return CHOOSING_PLAN
    
    await update.message.reply_text(f"✅ Usuario: *{username}*\n\nAhora envía tu *CONTRASEÑA*:", parse_mode="Markdown")
    return PREMIUM_PASSWORD

async def premium_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = context.user_data.get("premium_username_attempt", "")
    password = update.message.text.strip()
    
    if username in PREMIUM_USERS and PREMIUM_USERS[username]["password"] == password:
        if datetime.now() > PREMIUM_USERS[username]["expires"]:
            await update.message.reply_text("❌ Licencia expirada.")
            return await start(update, context)
        
        active_sessions[uid] = username
        days_left = max(0, (PREMIUM_USERS[username]["expires"] - datetime.now()).days)
        await update.message.reply_text(f"✅ *¡BIENVENIDO {username.upper()}!*\n\n⏰ Licencia: *{days_left} días*", parse_mode="Markdown")
        return await show_premium_menu(update, context)
    else:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
        await update.message.reply_text("❌ Contraseña incorrecta.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_PLAN

async def forgot_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔐 *RECUPERAR CONTRASEÑA*\n\nEnvía:\n*Nombre y Apellido:*\n*Email:*\n*Teléfono:*", parse_mode="Markdown")
    return FORGOT_PASSWORD

async def process_forgot_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = update.message.text
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
    await update.message.reply_text(f"✅ Solicitud recibida.\n\n📧 {ADMIN_EMAIL}", reply_markup=InlineKeyboardMarkup(keyboard))
    logger.info(f"Recuperación:\n{user_data}")
    return CHOOSING_PLAN

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("💳 *COMPRAR PREMIUM*\n\nEnvía:\n*Nombre:*\n*Celular:*\n*Email:*", parse_mode="Markdown")
    return PREMIUM_BUY_DATA

async def premium_buy_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = update.message.text
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_start")]]
    text = f"✅ *DATOS RECIBIDOS*\n\n💰 Paga $27 USD a:\n```THEGITANO2AX.PF```\n\n📧 Envía comprobante a:\n```{ADMIN_EMAIL}```\n\n{FIRMA_TEXTO}"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    logger.info(f"Compra:\n{user_data}")
    return CHOOSING_PLAN

async def show_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_premium_active(uid):
        return await plan_premium(update, context)
    info = get_premium_info(uid)
    keyboard = [
        [InlineKeyboardButton("📝 Texto a Voz", callback_data="premium_texto")],
        [InlineKeyboardButton("📄 Traducir Documentos", callback_data="premium_documento")],
        [InlineKeyboardButton("🎙️ Documentos a Voz", callback_data="premium_doc_voz")],
        [InlineKeyboardButton("🔊 Traducir Audio", callback_data="premium_audio")],
        [InlineKeyboardButton("🚪 Cerrar Sesión", callback_data="premium_logout")]
    ]
    text = f"✨ *BIENVENIDO {info['name'].upper()}* ✨\n\n⏰ *{info['days_left']} días* restantes\n\n💎 *MENÚ PREMIUM*"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def free_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not can_use_free(uid, "texto"):
        keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ Ya usaste FREE.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_PLAN
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("📝 *TEXTO A VOZ*\n\n🔄 ES → EN o EN → ES\n\nEnvía tu texto:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
    await query.edit_message_text("📝 *TEXTO A VOZ*\n\n🔄 ES → EN o EN → ES\n\nEnvía tu texto:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def free_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not can_use_free(uid, "documento"):
        keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ Ya usaste FREE.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_PLAN
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "translate"
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("📄 *TRADUCTOR DE DOCUMENTOS*\n\n🔄 ES ↔ EN\n\nEnvía .docx o .pdf:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "translate"
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
    await query.edit_message_text("📄 *TRADUCTOR DE DOCUMENTOS*\n\n🔄 ES ↔ EN\n\nEnvía .docx o .pdf:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def free_doc_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not can_use_free(uid, "doc_voz"):
        keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ Ya usaste FREE.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_PLAN
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "voice"
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("🎙️ *DOCUMENTOS A VOZ*\n\n🔄 ES ↔ EN\n\nEnvía .docx o .pdf:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_doc_voz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_document"] = True
    context.user_data["document_mode"] = "voice"
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
    await query.edit_message_text("🎙️ *DOCUMENTOS A VOZ*\n\n🔄 ES ↔ EN\n\nEnvía .docx o .pdf:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def free_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not can_use_free(uid, "audio"):
        keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ Ya usaste FREE.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_PLAN
    context.user_data["waiting_audio"] = True
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("🔊 *TRADUCTOR DE AUDIO*\n\n🔄 ES ↔ EN\n\nEnvía nota de voz:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_audio"] = True
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
    await query.edit_message_text("🔊 *TRADUCTOR DE AUDIO*\n\n🔄 ES ↔ EN\n\nEnvía nota de voz:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.user_data.get("waiting_text", False):
        return
    
    try:
        processing_msg = await update.message.reply_text("⏳ Procesando...")
        text = update.message.text
        
        lang = detect_language(text)
        logger.info(f"📊 TEXTO A VOZ - Idioma detectado: {lang}")
        
        if lang == "es" or lang.startswith("es"):
            translated = translate_text(text, source="es", target="en")
            audio_lang = "en"
            lang_display = "🇪🇸→🇺🇸"
            logger.info("✅ Español detectado → Audio en INGLÉS")
        else:
            translated = translate_text(text, source="en", target="es")
            audio_lang = "es"
            lang_display = "🇺🇸→🇪🇸"
            logger.info("✅ Inglés detectado → Audio en ESPAÑOL")
        
        await update.message.reply_text(f"{lang_display} *Traducción:*\n\n{translated}", parse_mode="Markdown")
        
        audio = tts(translated, audio_lang)
        if audio:
            await update.message.reply_voice(audio, caption=f"{lang_display} Audio traducido")
        
        if not context.user_data.get("is_premium", False):
            mark_free_used(uid, "texto")
        
        if not context.user_data.get("is_premium", False) and all_free_used(uid):
            keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
            await update.message.reply_text(f"✅ Ya usaste FREE\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
            context.user_data["waiting_text"] = False
        else:
            back = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
            keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data=back)]]
            await update.message.reply_text(f"✅ Listo. Envía otro texto o vuelve.\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
        
        await processing_msg.delete()
    except Exception as e:
        logger.error(f"❌ Error texto: {e}")
        await update.message.reply_text("❌ Error.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.user_data.get("waiting_document", False):
        return
    
    try:
        doc = update.message.document
        document_mode = context.user_data.get("document_mode", "translate")
        
        processing_msg = await update.message.reply_text(f"⏳ Procesando documento...")
        file = await context.bot.get_file(doc.file_id)
        data = await file.download_as_bytearray()
        
        if doc.file_name.endswith(".docx"):
            text = extract_text_from_docx(data)
        elif doc.file_name.endswith(".pdf"):
            text = extract_text_from_pdf(data)
        else:
            await update.message.reply_text("❌ Solo .docx o .pdf")
            await processing_msg.delete()
            return
        
        if not text:
            await update.message.reply_text("❌ No se extrajo texto.")
            await processing_msg.delete()
            return
        
        lang = detect_language(text[:500])
        
        if lang == "es" or lang.startswith("es"):
            target_lang = "en"
            lang_display = "🇪🇸→🇺🇸"
            audio_lang = "en"
        else:
            target_lang = "es"
            lang_display = "🇺🇸→🇪🇸"
            audio_lang = "es"
        
        translated_text = translate_text(text, source=lang, target=target_lang)
        
        if document_mode == "translate":
            if doc.file_name.endswith(".docx"):
                translated_file = translate_docx(data, source_lang=lang, target_lang=target_lang)
            else:
                translated_file = translate_pdf_to_docx(data, source_lang=lang, target_lang=target_lang)
            
            if translated_file:
                filename = f"traducido_{lang_display.replace('🇪🇸', 'ES').replace('🇺🇸', 'EN').replace('→', '_')}_{doc.file_name.replace('.pdf', '.docx')}"
                await update.message.reply_document(document=translated_file, filename=filename, caption=f"{lang_display} Documento traducido\n\n{FIRMA_TEXTO}")
            else:
                await update.message.reply_text("❌ Error al traducir.")
                await processing_msg.delete()
                return
            
            if not context.user_data.get("is_premium", False):
                mark_free_used(uid, "documento")
        else:
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
```

**También actualiza tu `requirements.txt`:**
```
python-telegram-bot==20.7
python-docx
PyPDF2
deep-translator
gtts
langdetect
SpeechRecognition
pydub
