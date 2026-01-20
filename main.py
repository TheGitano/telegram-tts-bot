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
FIRMA_TEXTO = "🦅 𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸 🦅"

# Usuarios Premium (agregar después del pago)
PREMIUM_USERS = {
    "Gitano": {"password": "8376", "name": "El Gitano", "expires": datetime(2099, 12, 31)}
}

active_sessions = {}
free_usage = {}

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ================= ESTADOS =================
CHOOSING_PLAN, PREMIUM_USERNAME, PREMIUM_PASSWORD, PREMIUM_BUY_DATA = range(4)

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
        free_usage[uid] = {"texto": False, "documento": False}
    return not free_usage[uid][function_name]

def mark_free_used(uid, function_name):
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False}
    free_usage[uid][function_name] = True

def all_free_used(uid):
    if uid not in free_usage:
        return False
    return free_usage[uid]["texto"] and free_usage[uid]["documento"]

def translate_text(text, target="es"):
    try:
        if not text or len(text.strip()) == 0:
            return ""
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="auto", target=target)
        if len(text) > 4500:
            chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
            return " ".join([translator.translate(chunk) for chunk in chunks])
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Error traducción: {e}")
        return text

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
                paragraph.text = translate_text(paragraph.text, target)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        cell.text = translate_text(cell.text, target)
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
        free_usage[uid] = {"texto": False, "documento": False}
    
    keyboard = [[InlineKeyboardButton("🆓 FREE", callback_data="plan_free"), InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")]]
    text = ("━━━━━━━━━━━━━━━━━━━━━━\n✨ 𝗕𝗜𝗘𝗡𝗩𝗘𝗡𝗜𝗗𝗢 ✨\n━━━━━━━━━━━━━━━━━━━━━━\n\n🎯 *BOT CREADO POR:*\n🦅 *𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸* 🦅\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n📋 *FUNCIONALIDADES:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n🔹 Traducir texto a español latino\n🔹 Traducir documentos Word/PDF\n"
            "🔹 Convertir texto a voz con acento latino\n\n━━━━━━━━━━━━━━━━━━━━━━\n💡 *SELECCIONA TU PLAN:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n🆓 *FREE:* 1 uso por cada función\n💎 *PREMIUM:* Uso ilimitado por 30 días\n\n👇 *Elige una opción abajo:* 👇")
    
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
        await query.edit_message_text("━━━━━━━━━━━━━━━━━━━━━━\n🎊 *¡ULALA!* 🎊\n━━━━━━━━━━━━━━━━━━━━━━\n\n✅ *Ya utilizaste tu prueba FREE*\n\n"
                                      "Para seguir utilizando mis servicios,\npor favor compra la licencia PREMIUM.\n\n━━━━━━━━━━━━━━━━━━━━━━\n💎 *PREMIUM - $27 USD/30 días*\n━━━━━━━━━━━━━━━━━━━━━━",
                                      reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return CHOOSING_PLAN
    
    texto_status = "✅" if not free_usage[uid]["texto"] else "❌"
    doc_status = "✅" if not free_usage[uid]["documento"] else "❌"
    keyboard = [[InlineKeyboardButton(f"{texto_status} 📝 Texto a Voz", callback_data="free_texto")],
                [InlineKeyboardButton(f"{doc_status} 📄 Traducir Documentos", callback_data="free_documento")],
                [InlineKeyboardButton("💎 Actualizar a PREMIUM", callback_data="plan_premium")],
                [InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_start")]]
    
    text = f"━━━━━━━━━━━━━━━━━━━━━━\n🆓 *MODO FREE* 🆓\n━━━━━━━━━━━━━━━━━━━━━━\n\nTienes *1 uso* por cada función:\n\n{texto_status} *Texto a Voz*\n{doc_status} *Traducir Documentos*\n\n━━━━━━━━━━━━━━━━━━━━━━\n👇 *Selecciona una opción:* 👇\n━━━━━━━━━━━━━━━━━━━━━━"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

# ================= PREMIUM =================

async def plan_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    
    if is_premium_active(uid):
        return await show_premium_menu(update, context)
    
    keyboard = [[InlineKeyboardButton("🔑 INGRESAR", callback_data="premium_login")],
                [InlineKeyboardButton("💰 COMPRAR PREMIUM", callback_data="buy_premium")],
                [InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_start")]]
    
    text = ("━━━━━━━━━━━━━━━━━━━━━━\n💎 *PREMIUM* 💎\n━━━━━━━━━━━━━━━━━━━━━━\n\n```\n"
            "██████╗ ██████╗ ███████╗███╗   ███╗██╗██╗   ██╗███╗   ███╗\n"
            "██╔══██╗██╔══██╗██╔════╝████╗ ████║██║██║   ██║████╗ ████║\n"
            "██████╔╝██████╔╝█████╗  ██╔████╔██║██║██║   ██║██╔████╔██║\n"
            "██╔═══╝ ██╔══██╗██╔══╝  ██║╚██╔╝██║██║██║   ██║██║╚██╔╝██║\n"
            "██║     ██║  ██║███████╗██║ ╚═╝ ██║██║╚██████╔╝██║ ╚═╝ ██║\n"
            "╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝╚═╝ ╚═════╝ ╚═╝     ╚═╝\n```\n\n"
            "✨ *BENEFICIOS:*\n━━━━━━━━━━━━━━━━━━━━━━\n✅ Uso ilimitado de todas las funciones\n✅ Sin restricciones\n✅ Soporte prioritario\n✅ Acceso por 30 días\n\n💵 *PRECIO:* $27 USD / 30 días\n\n━━━━━━━━━━━━━━━━━━━━━━")
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "```\n"
        "╔═══════════════════════════════════╗\n"
        "║                                   ║\n"
        "║         🔐 INGRESAR 🔐            ║\n"
        "║                                   ║\n"
        "║   SISTEMA DE AUTENTICACIÓN v2.0   ║\n"
        "║        [ACCESO RESTRINGIDO]       ║\n"
        "║                                   ║\n"
        "╚═══════════════════════════════════╝\n"
        "```\n\n"
        "Envía tus credenciales en este formato:\n\n"
        "```\n"
        "User: tu_usuario\n"
        "Password: tu_contraseña\n"
        "```",
        parse_mode="Markdown"
    )
    return PREMIUM_USERNAME

async def premium_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa las credenciales enviadas juntas"""
    uid = update.effective_user.id
    credentials = update.message.text.strip()
    
    # Intentar extraer usuario y contraseña del texto
    lines = credentials.split('\n')
    username = None
    password = None
    
    for line in lines:
        line = line.strip()
        # Buscar usuario
        if 'user:' in line.lower() or 'usuario:' in line.lower():
            username = line.split(':', 1)[1].strip()
        # Buscar contraseña
        elif 'password:' in line.lower() or 'contraseña:' in line.lower() or 'pass:' in line.lower():
            password = line.split(':', 1)[1].strip()
    
    # Validar credenciales
    if username and password and username in PREMIUM_USERS and PREMIUM_USERS[username]["password"] == password:
        if datetime.now() > PREMIUM_USERS[username]["expires"]:
            await update.message.reply_text(
                "```\n"
                "╔═══════════════════════════════════╗\n"
                "║      ⚠️ LICENCIA EXPIRADA ⚠️      ║\n"
                "╚═══════════════════════════════════╝\n"
                "```\n\n"
                "❌ *Tu licencia Premium ha expirado.*\n\n"
                "Por favor, renueva tu suscripción.",
                parse_mode="Markdown"
            )
            return await start(update, context)
        
        # Login exitoso
        active_sessions[uid] = username
        name = PREMIUM_USERS[username]["name"]
        days_left = max(0, (PREMIUM_USERS[username]["expires"] - datetime.now()).days)
        
        await update.message.reply_text(
            "```\n"
            "╔═══════════════════════════════════╗\n"
            "║      ✅ ACCESO AUTORIZADO ✅      ║\n"
            "║                                   ║\n"
            "║   Verificando credenciales...     ║\n"
            "║   [████████████████████] 100%     ║\n"
            "║                                   ║\n"
            "╚═══════════════════════════════════╝\n"
            "```\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎉 *¡BIENVENIDO {username.upper()}!* 🎉\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"✅ Inicio de sesión exitoso\n"
            f"⏰ Te quedan *{days_left} días* de licencia\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━",
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
            "║                                   ║\n"
            "╚═══════════════════════════════════╝\n"
            "```\n\n"
            "❌ *Usuario o contraseña incorrectos.*\n\n"
            "Intenta nuevamente.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return CHOOSING_PLAN

async def premium_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Esta función ya no se usa pero la dejamos por compatibilidad"""
    return CHOOSING_PLAN

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("━━━━━━━━━━━━━━━━━━━━━━\n💳 *COMPRAR PREMIUM* 💳\n━━━━━━━━━━━━━━━━━━━━━━\n\nPor favor, envía tus datos en el siguiente formato:\n\n*Nombre y Apellido:*\n*Número Celular Completo:*\n*Correo Electrónico:*\n\n"
                                  "━━━━━━━━━━━━━━━━━━━━━━\n*Ejemplo:*\n```\nNombre y Apellido: Juan Pérez\nNúmero Celular Completo: +54 9 11 1234-5678\nCorreo Electrónico: juan@email.com\n```\n━━━━━━━━━━━━━━━━━━━━━━\n\n📝 Envía todos los datos en un solo mensaje:", parse_mode="Markdown")
    return PREMIUM_BUY_DATA

async def premium_buy_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = update.message.text
    keyboard = [[InlineKeyboardButton("🔙 Volver al Menú Inicial", callback_data="back_start")]]
    text = (f"━━━━━━━━━━━━━━━━━━━━━━\n✅ *DATOS RECIBIDOS* ✅\n━━━━━━━━━━━━━━━━━━━━━━\n\n📋 *Tus datos:*\n```\n{user_data}\n```\n\n━━━━━━━━━━━━━━━━━━━━━━\n💰 *INSTRUCCIONES DE PAGO:*\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ *Realiza el pago de $27 USD* al alias:\n```THEGITANO2AX.PF```\n\n2️⃣ *Envía el comprobante de pago* a:\n```corporatebusinessunitedstates@gmail.com```\n\n3️⃣ *Incluye en el correo:*\n   • Tus datos completos\n   • Captura del comprobante de pago\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n⏰ *ACTIVACIÓN:*\n━━━━━━━━━━━━━━━━━━━━━━\n\nUna vez confirmado tu pago, recibirás:\n✉️ *Usuario y contraseña* vía Telegram\n✉️ *Credenciales* vía correo electrónico\n\nTu cuenta será activada en *menos de 24 horas*.\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
            f"¡Gracias por tu compra! {FIRMA_TEXTO}\n━━━━━━━━━━━━━━━━━━━━━━")
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    logger.info(f"Nueva solicitud PREMIUM:\n{user_data}")
    return CHOOSING_PLAN

async def show_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_premium_active(uid):
        return await plan_premium(update, context)
    
    info = get_premium_info(uid)
    keyboard = [[InlineKeyboardButton("📝 Texto a Voz", callback_data="premium_texto")],
                [InlineKeyboardButton("📄 Traducir Documentos", callback_data="premium_documento")],
                [InlineKeyboardButton("⚙️ Configuración", callback_data="premium_config")],
                [InlineKeyboardButton("❓ Ayuda", callback_data="premium_help")],
                [InlineKeyboardButton("🚪 Cerrar Sesión", callback_data="premium_logout")]]
    
    text = f"━━━━━━━━━━━━━━━━━━━━━━\n✨ *BIENVENIDO SR. {info['name'].upper()}* ✨\n━━━━━━━━━━━━━━━━━━━━━━\n\n⏰ Te quedan *{info['days_left']} días* de tu licencia Premium\n\n━━━━━━━━━━━━━━━━━━━━━━\n💎 *MENÚ PREMIUM* 💎\n━━━━━━━━━━━━━━━━━━━━━━\n\nSelecciona una opción:"
    
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
        keyboard = [[InlineKeyboardButton("💎 Comprar PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ *Ya usaste tu prueba FREE de esta función.*\n\nCompra PREMIUM para uso ilimitado.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return CHOOSING_PLAN
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("📝 *TEXTO A VOZ*\n\nEnvía el texto que deseas convertir a audio:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="premium_menu")]]
    await query.edit_message_text("📝 *TEXTO A VOZ*\n\nEnvía el texto que deseas convertir a audio:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def free_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    if not can_use_free(uid, "documento"):
        keyboard = [[InlineKeyboardButton("💎 Comprar PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text("❌ *Ya usaste tu prueba FREE de esta función.*\n\nCompra PREMIUM para uso ilimitado.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        return CHOOSING_PLAN
    context.user_data["waiting_document"] = True
    context.user_data["is_premium"] = False
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    await query.edit_message_text("📄 *TRADUCIR DOCUMENTOS*\n\nEnvía un documento Word (.docx) o PDF para traducir:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

async def premium_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["waiting_document"] = True
    context.user_data["is_premium"] = True
    keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="premium_menu")]]
    await query.edit_message_text("📄 *TRADUCIR DOCUMENTOS*\n\nEnvía un documento Word (.docx) o PDF para traducir:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return CHOOSING_PLAN

# ================= HANDLERS =================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.user_data.get("waiting_text", False):
        return
    try:
        processing_msg = await update.message.reply_text("⏳ Generando audio...")
        audio = tts(update.message.text, "es")
        if audio:
            await update.message.reply_voice(audio)
            if not context.user_data.get("is_premium", False):
                mark_free_used(uid, "texto")
            if not context.user_data.get("is_premium", False) and all_free_used(uid):
                keyboard = [[InlineKeyboardButton("💎 COMPRAR PREMIUM", callback_data="plan_premium")]]
                await update.message.reply_text(f"━━━━━━━━━━━━━━━━━━━━━━\n🎊 *¡ULALA!* 🎊\n━━━━━━━━━━━━━━━━━━━━━━\n\n✅ *Ya utilizaste tu prueba FREE*\n\nPara seguir utilizando mis servicios,\npor favor compra la licencia PREMIUM.\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            else:
                back_data = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=back_data)]]
                await update.message.reply_text(f"✅ ¡Listo!\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text("❌ Error al generar el audio.")
        await processing_msg.delete()
        context.user_data["waiting_text"] = False
    except Exception as e:
        logger.error(f"Error handle_text: {e}")
        await update.message.reply_text("❌ Error. Intenta de nuevo.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.user_data.get("waiting_document", False):
        return
    try:
        doc = update.message.document
        processing_msg = await update.message.reply_text(f"⏳ Procesando: {doc.file_name}...")
        file = await context.bot.get_file(doc.file_id)
        data = await file.download_as_bytearray()
        
        if doc.file_name.endswith(".docx"):
            translated_file = translate_docx(data, "es")
            if translated_file:
                await update.message.reply_document(document=translated_file, filename=f"traducido_{doc.file_name}")
            else:
                await update.message.reply_text("❌ Error al traducir el documento.")
                await processing_msg.delete()
                return
        elif doc.file_name.endswith(".pdf"):
            text = extract_text_from_pdf(data)
            if text:
                translated_text = translate_text(text, "es")
                audio = tts(translated_text, "es")
                if audio:
                    await update.message.reply_voice(audio)
                else:
                    await update.message.reply_text(f"*Traducción:*\n\n{translated_text[:4000]}", parse_mode="Markdown")
            else:
                await update.message.reply_text("❌ No se pudo extraer texto del PDF.")
                await processing_msg.delete()
                return
        else:
            await update.message.reply_text("❌ Formato no soportado. Solo .docx o .pdf")
            await processing_msg.delete()
            return
        
        if not context.user_data.get("is_premium", False):
            mark_free_used(uid, "documento")
        if not context.user_data.get("is_premium", False) and all_free_used(uid):
            keyboard = [[InlineKeyboardButton("💎 COMPRAR PREMIUM", callback_data="plan_premium")]]
            await update.message.reply_text(f"━━━━━━━━━━━━━━━━━━━━━━\n🎊 *¡ULALA!* 🎊\n━━━━━━━━━━━━━━━━━━━━━━\n\n✅ *Ya utilizaste tu prueba FREE*\n\nPara seguir utilizando mis servicios,\npor favor compra la licencia PREMIUM.\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            back_data = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=back_data)]]
            await update.message.reply_text(f"✅ ¡Documento procesado!\n\n{FIRMA_TEXTO}", reply_markup=InlineKeyboardMarkup(keyboard))
        await processing_msg.delete()
        context.user_data["waiting_document"] = False
    except Exception as e:
        logger.error(f"Error handle_document: {e}")
        await update.message.reply_text("❌ Error. Intenta de nuevo.")

# ================= CALLBACKS =================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "back_start":
        context.user_data.clear()
        await start(update, context)
    elif data == "plan_free":
        await plan_free(update, context)
    elif data == "plan_premium":
        await plan_premium(update, context)
    elif data == "buy_premium":
        await buy_premium(update, context)
    elif data == "premium_login":
        await premium_login(update, context)
    elif data == "free_texto":
        await free_texto(update, context)
    elif data == "free_documento":
        await free_documento(update, context)
    elif data == "premium_menu":
        await show_premium_menu(update, context)
    elif data == "premium_texto":
        await premium_texto(update, context)
    elif data == "premium_documento":
        await premium_documento(update, context)
    elif data == "premium_config":
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
        await query.edit_message_text("⚙️ *CONFIGURACIÓN*\n\nPróximamente disponible:\n• Idioma de destino\n• Velocidad de voz\n• Formato de audio", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "premium_help":
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
        await query.edit_message_text("❓ *AYUDA*\n\n*Cómo usar:*\n1️⃣ Selecciona una función\n2️⃣ Envía tu contenido\n3️⃣ Recibe el resultado\n\n*Soporte:*\n📧 corporatebusinessunitedstates@gmail.com", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    elif data == "premium_logout":
        uid = update.effective_user.id
        if uid in active_sessions:
            del active_sessions[uid]
        await query.edit_message_text("✅ *Sesión cerrada correctamente.*\n\nHasta pronto!", parse_mode="Markdown")
        await start(update, context)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ Error inesperado. Usa /start para reiniciar.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TOKEN NO CONFIGURADO")
        return
    
    logger.info("🚀 Iniciando El Gitano Bot...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_PLAN: [CallbackQueryHandler(button_callback)],
            PREMIUM_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_username)],
            PREMIUM_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_password)],
            PREMIUM_BUY_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_buy_data)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_error_handler(error_handler)
    
    logger.info("✅ Bot iniciado correctamente")
    logger.info("🦅 El Gitano Bot está listo")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
