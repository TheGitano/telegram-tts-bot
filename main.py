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

# ================= CONFIGURACIÓN =================
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

# ================= UTILIDADES =================

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
        free_usage[uid] = {"texto": False, "documento": False, "audio": False}
    return not free_usage[uid][function_name]

def mark_free_used(uid, function_name):
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False, "audio": False}
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
        return detect(text)
    except:
        return "unknown"

def tts(text, lang="es"):
    try:
        audio = io.BytesIO()
        if len(text) > 5000:
            text = text[:5000] + "..."
        gTTS(text=text, lang=lang, slow=False).write_to_fp(audio)
        audio.seek(0)
        return audio
    except Exception as e:
        logger.error(f"Error TTS: {e}")
        return None

def extract_text_from_pdf(file_bytes):
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    except Exception as e:
        logger.error(f"Error PDF: {e}")
        return ""

def translate_docx(file_bytes, target="es"):
    try:
        doc = Document(io.BytesIO(file_bytes))
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                paragraph.text = translate_text(paragraph.text, target=target)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        cell.text = translate_text(cell.text, target=target)
        out_stream = io.BytesIO()
        doc.save(out_stream)
        out_stream.seek(0)
        return out_stream
    except Exception as e:
        logger.error(f"Error DOCX: {e}")
        return None

# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data.clear()
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False, "audio": False}
    
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
        "📝 Texto a Voz 🗣️\n"
        "🌐 Traductor Bidireccional (ES ↔ EN)\n"
        "📄 Traducir Documentos Word/PDF\n"
        "🎙️ Traducir Audios de Voz\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *SELECCIONA TU PLAN:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🆓 *FREE:* 1 uso por función\n"
        "💎 *PREMIUM:* Uso ilimitado 30 días\n\n"
        "👇 *Elige una opción:* 👇"
    )
    
    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

# ================= FREE =================

async def plan_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    
    if all_free_used(uid):
        keyboard = [[InlineKeyboardButton("💎 COMPRAR PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n🎊 *¡ULALA!* 🎊\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Ya utilizaste tu prueba FREE*\n\nPara seguir usando, compra PREMIUM.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n💎 *PREMIUM - $27 USD/30 días*\n━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
        return CHOOSING_PLAN
    
    texto_status = "✅" if not free_usage[uid]["texto"] else "❌"
    doc_status = "✅" if not free_usage[uid]["documento"] else "❌"
    audio_status = "✅" if not free_usage[uid]["audio"] else "❌"
    
    keyboard = [
        [InlineKeyboardButton(f"{texto_status} 📝 Texto a Voz 🗣️", callback_data="free_texto")],
        [InlineKeyboardButton(f"{doc_status} 📄 Traducir Documentos", callback_data="free_documento")],
        [InlineKeyboardButton(f"{audio_status} 🎙️ Traducir Audio", callback_data="free_audio")],
        [InlineKeyboardButton("💎 Actualizar a PREMIUM", callback_data="plan_premium")],
        [InlineKeyboardButton("🔙 Volver", callback_data="back_start")]
    ]
    
    text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n🆓 *MODO FREE* 🆓\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Tienes *1 uso* por función:\n\n"
        f"{texto_status} *Texto a Voz*\n{doc_status} *Traducir Documentos*\n{audio_status} *Traducir Audio*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n👇 *Selecciona:* 👇\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

# ================= PREMIUM =================

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
        "```\n"
        "██████╗ ██████╗ ███████╗███╗   ███╗██╗██╗   ██╗███╗   ███╗\n"
        "██╔══██╗██╔══██╗██╔════╝████╗ ████║██║██║   ██║████╗ ████║\n"
        "██████╔╝██████╔╝█████╗  ██╔████╔██║██║██║   ██║██╔████╔██║\n"
        "██╔═══╝ ██╔══██╗██╔══╝  ██║╚██╔╝██║██║██║   ██║██║╚██╔╝██║\n"
        "██║     ██║  ██║███████╗██║ ╚═╝ ██║██║╚██████╔╝██║ ╚═╝ ██║\n"
        "╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝ ╚═════╝ ╚═╝     ╚═╝\n"
        "```\n\n✨ *BENEFICIOS:*\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Uso ilimitado\n✅ Traducción bidireccional\n✅ Sin restricciones\n✅ Soporte prioritario\n\n"
        "💵 *$27 USD / 30 días*\n━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data.clear()
    
    await query.edit_message_text(
        "```\n"
        "╔═══════════════════════════════════════════════╗\n"
        "║                                               ║\n"
        "║            🔐 LOGIN PREMIUM 🔐                ║\n"
        "║                                               ║\n"
        "║     ███████╗██╗   ██╗███████╗████████╗       ║\n"
        "║     ██╔════╝╚██╗ ██╔╝██╔════╝╚══██╔══╝       ║\n"
        "║     ███████╗ ╚████╔╝ ███████╗   ██║          ║\n"
        "║     ╚════██║  ╚██╔╝  ╚════██║   ██║          ║\n"
        "║     ███████║   ██║   ███████║   ██║          ║\n"
        "║     ╚══════╝   ╚═╝   ╚══════╝   ╚═╝          ║\n"
        "║                                               ║\n"
        "║        SISTEMA DE AUTENTICACIÓN v3.0          ║\n"
        "║           [ACCESO RESTRINGIDO]                ║\n"
        "║                                               ║\n"
        "╚═══════════════════════════════════════════════╝\n"
        "```\n\n"
        "🔹 **PASO 1:** Ingresa tu *USUARIO*\n"
        "🔹 **PASO 2:** Ingresa tu *CONTRASEÑA*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Por favor, envía tu *USUARIO* ahora:",
        parse_mode="Markdown"
    )
    
    return PREMIUM_USERNAME

async def premium_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    context.user_data["premium_username_attempt"] = username
    
    if username not in PREMIUM_USERS:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
        await update.message.reply_text(
            "```\n"
            "╔═══════════════════════════════════╗\n"
            "║       ❌ USUARIO NO EXISTE ❌    ║\n"
            "╚═══════════════════════════════════╝\n"
            "```\n\n"
            f"❌ El usuario '{username}' no está registrado.\n\nIntenta nuevamente.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return CHOOSING_PLAN
    
    await update.message.reply_text(
        "```\n"
        "╔═══════════════════════════════════╗\n"
        "║       🔑 CONTRASEÑA 🔑            ║\n"
        "║                                   ║\n"
        "║   [●●●●●●●●●●●●●●●●●●●●]         ║\n"
        "║                                   ║\n"
        "╚═══════════════════════════════════╝\n"
        "```\n\n"
        f"✅ Usuario: *{username}*\n\n"
        "Ahora ingresa tu *CONTRASEÑA*:",
        parse_mode="Markdown"
    )
    return PREMIUM_PASSWORD

async def premium_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = context.user_data.get("premium_username_attempt", "")
    password = update.message.text.strip()
    
    if username in PREMIUM_USERS and PREMIUM_USERS[username]["password"] == password:
        if datetime.now() > PREMIUM_USERS[username]["expires"]:
            await update.message.reply_text(
                "```\n╔═══════════════════════════════════╗\n"
                "║      ⚠️ LICENCIA EXPIRADA ⚠️      ║\n"
                "╚═══════════════════════════════════╝\n```\n\n"
                "❌ Tu licencia expiró.\n\nRenueva tu suscripción.",
                parse_mode="Markdown"
            )
            return await start(update, context)
        
        active_sessions[uid] = username
        days_left = max(0, (PREMIUM_USERS[username]["expires"] - datetime.now()).days)
        
        await update.message.reply_text(
            "```\n"
            "╔═══════════════════════════════════════════════╗\n"
            "║      ✅ ACCESO AUTORIZADO ✅                  ║\n"
            "║                                               ║\n"
            "║   Verificando credenciales...                 ║\n"
            "║   [████████████████████████████] 100%         ║\n"
            "║                                               ║\n"
            "║        >> CONEXIÓN ESTABLECIDA <<            ║\n"
            "║                                               ║\n"
            "╚═══════════════════════════════════════════════╝\n"
            "```\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n🎉 *¡BIENVENIDO {username.upper()}!* 🎉\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Login exitoso\n⏰ Licencia: *{days_left} días*\n\n━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown"
        )
        return await show_premium_menu(update, context)
    else:
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
        await update.message.reply_text(
            "```\n"
            "╔═══════════════════════════════════╗\n"
            "║       ❌ ACCESO DENEGADO ❌       ║\n"
            "║                                   ║\n"
            "║    Credenciales inválidas         ║\n"
            "║      >> ERROR 401 <<              ║\n"
            "║                                   ║\n"
            "╚═══════════════════════════════════╝\n"
            "```\n\n❌ Usuario/contraseña incorrectos.",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
        return CHOOSING_PLAN

async def forgot_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "```\n"
        "╔═══════════════════════════════════╗\n"
        "║    🔐 RECUPERAR CONTRASEÑA 🔐    ║\n"
        "║                                   ║\n"
        "║   Sistema de Recuperación v1.0    ║\n"
        "║                                   ║\n"
        "╚═══════════════════════════════════╝\n"
        "```\n\n"
        "Envía los datos de tu registro:\n\n"
        "*Nombre y Apellido:*\n*Correo Electrónico:*\n*Teléfono:*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\nEnvía todo en un mensaje:",
        parse_mode="Markdown"
    )
    return FORGOT_PASSWORD

async def process_forgot_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = update.message.text
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="plan_premium")]]
    await update.message.reply_text(
        f"✅ *Solicitud Recibida*\n\nDatos enviados a:\n📧 {ADMIN_EMAIL}\n\n"
        "Recibirás nueva contraseña en <24h.",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )
    logger.info(f"Recuperación contraseña:\n{user_data}")
    return CHOOSING_PLAN

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n💳 *COMPRAR PREMIUM* 💳\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Envía tus datos:\n\n*Nombre y Apellido:*\n*Número Celular:*\n*Correo Electrónico:*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n📝 Todo en un mensaje:",
        parse_mode="Markdown"
    )
    return PREMIUM_BUY_DATA

async def premium_buy_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = update.message.text
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="back_start")]]
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n✅ *DATOS RECIBIDOS* ✅\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 Tus datos:\n```\n{user_data}\n```\n\n━━━━━━━━━━━━━━━━━━━━━━\n💰 *INSTRUCCIONES:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n1️⃣ Paga *$27 USD*:\n```THEGITANO2AX.PF```\n\n"
        "2️⃣ Envía comprobante a:\n```corporatebusinessunitedstates@gmail.com```\n\n"
        "3️⃣ Incluye datos + captura\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ Activación <24h\n✉️ Recibirás usuario/pass\n\n{FIRMA_TEXTO}"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    logger.info(f"Solicitud PREMIUM:\n{user_data}")
    return CHOOSING_PLAN

async def show_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_premium_active(uid):
        return await plan_premium(update, context)
    info = get_premium_info(uid)
    keyboard = [
        [InlineKeyboardButton("📝 Texto a Voz 🗣️", callback_data="premium_texto")],
        [InlineKeyboardButton("📄 Traducir Documentos", callback_data="premium_documento")],
        [InlineKeyboardButton("🎙️ Traducir Audio", callback_data="premium_audio")],
        [InlineKeyboardButton("⚙️ Configuración", callback_data="premium_config")],
        [InlineKeyboardButton("🚪 Cerrar Sesión", callback_data="premium_logout")]
    ]
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n✨ *BIENVENIDO {info['name'].upper()}* ✨\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏰ *{info['days_left']} días* restantes\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 *MENÚ PREMIUM* 💎\n━━━━━━━━━━━━━━━━━━━━━━\n\nSelecciona:"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

# ================= FUNCIONES =================

async def free_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not can_use_free(uid, "texto"):
        keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ Ya usaste FREE.\n\nCompra PREMIUM.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_PLAN
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("📝 *TEXTO A VOZ*\n\nEnvía texto (español o inglés):", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
    await query.edit_message_text("📝 *TEXTO A VOZ*\n\nEnvía texto (español o inglés):", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
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
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("📄 *DOCUMENTOS*\n\nEnvía Word/PDF:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_document"] = True
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
    await query.edit_message_text("📄 *DOCUMENTOS*\n\nEnvía Word/PDF:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def free_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not can_use_free(uid, "audio"):
        keyboard = [[InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ Ya usaste FREE.", reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSING_PLAN
    context.user_data["
