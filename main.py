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
from langdetect import detect
from gtts import gTTS

# ================= CONFIGURACIÓN =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIRMA_TEXTO = "🦅 𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸 🦅"

# Usuarios Premium autorizados (se agregarán manualmente después del pago)
PREMIUM_USERS = {}  # formato: {user_id: {"username": "nombre", "expires": datetime}}

# Control de uso FREE
free_usage = {}  # formato: {user_id: {"texto": usado, "documento": usado}}

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= ESTADOS DE CONVERSACIÓN =================
CHOOSING_PLAN, PREMIUM_NAME, PREMIUM_PHONE, PREMIUM_EMAIL = range(4)

# ================= UTILIDADES =================

def is_premium_user(uid):
    """Verifica si el usuario tiene Premium activo"""
    if uid not in PREMIUM_USERS:
        return False
    
    user_data = PREMIUM_USERS[uid]
    if datetime.now() > user_data["expires"]:
        return False
    
    return True

def get_days_remaining(uid):
    """Obtiene los días restantes de Premium"""
    if uid not in PREMIUM_USERS:
        return 0
    
    user_data = PREMIUM_USERS[uid]
    remaining = user_data["expires"] - datetime.now()
    return max(0, remaining.days)

def can_use_free(uid, function_name):
    """Verifica si puede usar la función en modo FREE"""
    if is_premium_user(uid):
        return True
    
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False}
    
    return not free_usage[uid][function_name]

def mark_free_used(uid, function_name):
    """Marca una función como usada en modo FREE"""
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False}
    
    free_usage[uid][function_name] = True

def all_free_used(uid):
    """Verifica si ya usó todas las funciones FREE"""
    if uid not in free_usage:
        return False
    
    return free_usage[uid]["texto"] and free_usage[uid]["documento"]

def translate_text(text, target="es"):
    """Traduce texto con manejo de errores"""
    try:
        if not text or len(text.strip()) == 0:
            return ""
        translator = GoogleTranslator(source="auto", target=target)
        max_length = 4500
        if len(text) > max_length:
            chunks = [text[i:i+max_length] for i in range(0, len(text), max_length)]
            return " ".join([translator.translate(chunk) for chunk in chunks])
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Error en traducción: {e}")
        return text

def tts(text, lang="es"):
    """Convierte texto a voz"""
    try:
        audio = io.BytesIO()
        max_chars = 5000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        gTTS(text=text, lang=lang, slow=False).write_to_fp(audio)
        audio.seek(0)
        return audio
    except Exception as e:
        logger.error(f"Error en TTS: {e}")
        return None

def extract_text_from_pdf(file_bytes):
    """Extrae texto de PDF"""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        return text
    except Exception as e:
        logger.error(f"Error extrayendo texto de PDF: {e}")
        return ""

def translate_docx(file_bytes, target="es"):
    """Traduce documento Word"""
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
        logger.error(f"Error traduciendo DOCX: {e}")
        return None

# ================= MENÚ INICIAL =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú de bienvenida espectacular"""
    uid = update.effective_user.id
    
    # Inicializar uso FREE si es necesario
    if uid not in free_usage:
        free_usage[uid] = {"texto": False, "documento": False}
    
    keyboard = [
        [
            InlineKeyboardButton("🆓 FREE", callback_data="plan_free"),
            InlineKeyboardButton("💎 PREMIUM", callback_data="plan_premium")
        ]
    ]
    
    welcome_text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✨ 𝗕𝗜𝗘𝗡𝗩𝗘𝗡𝗜𝗗𝗢 ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *BOT CREADO POR:*\n"
        "🦅 *𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸* 🦅\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 *FUNCIONALIDADES:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔹 Traducir texto a español latino\n"
        "🔹 Traducir documentos Word/PDF\n"
        "🔹 Convertir texto a voz con acento latino\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 *SELECCIONA TU PLAN:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🆓 *FREE:* 1 uso por cada función\n"
        "💎 *PREMIUM:* Uso ilimitado por 30 días\n\n"
        "👇 *Elige una opción abajo:* 👇"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return CHOOSING_PLAN

# ================= PLAN FREE =================

async def plan_free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú FREE con indicadores de uso"""
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    
    # Verificar si ya usó todo en FREE
    if all_free_used(uid):
        keyboard = [[InlineKeyboardButton("💎 COMPRAR PREMIUM", callback_data="plan_premium")]]
        
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🎊 *¡ULALA!* 🎊\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "✅ *Ya utilizaste tu prueba FREE*\n\n"
            "Para seguir utilizando mis servicios,\n"
            "por favor compra la licencia PREMIUM.\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "💎 *PREMIUM - $27 USD/30 días*\n"
            "━━━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return CHOOSING_PLAN
    
    # Construir menú con indicadores
    texto_status = "✅" if not free_usage[uid]["texto"] else "❌"
    doc_status = "✅" if not free_usage[uid]["documento"] else "❌"
    
    keyboard = [
        [InlineKeyboardButton(f"{texto_status} 📝 Texto a Voz", callback_data="free_texto")],
        [InlineKeyboardButton(f"{doc_status} 📄 Traducir Documentos", callback_data="free_documento")],
        [InlineKeyboardButton("💎 Actualizar a PREMIUM", callback_data="plan_premium")],
        [InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_start")]
    ]
    
    menu_text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🆓 *MODO FREE* 🆓\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Tienes *1 uso* por cada función:\n\n"
        f"{texto_status} *Texto a Voz*\n"
        f"{doc_status} *Traducir Documentos*\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "👇 *Selecciona una opción:* 👇\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await query.edit_message_text(
        menu_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return CHOOSING_PLAN

# ================= PLAN PREMIUM =================

async def plan_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra información de PREMIUM"""
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    
    # Si ya es PREMIUM, mostrar menú
    if is_premium_user(uid):
        return await show_premium_menu(update, context)
    
    keyboard = [
        [InlineKeyboardButton("💰 COMPRAR PREMIUM", callback_data="buy_premium")],
        [InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_start")]
    ]
    
    premium_text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 *PREMIUM* 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "```\n"
        "███████╗██╗  ██╗██╗████████╗███████╗\n"
        "██╔════╝██║  ██║██║╚══██╔══╝██╔════╝\n"
        "█████╗  ███████║██║   ██║   █████╗  \n"
        "██╔══╝  ██╔══██║██║   ██║   ██╔══╝  \n"
        "███████╗██║  ██║██║   ██║   ███████╗\n"
        "╚══════╝╚═╝  ╚═╝╚═╝   ╚═╝   ╚══════╝\n"
        "```\n\n"
        "✨ *BENEFICIOS:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ Uso ilimitado de todas las funciones\n"
        "✅ Sin restricciones\n"
        "✅ Soporte prioritario\n"
        "✅ Acceso por 30 días\n\n"
        "💵 *PRECIO:* $27 USD / 30 días\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await query.edit_message_text(
        premium_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return CHOOSING_PLAN

async def buy_premium(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de compra PREMIUM"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💳 *PROCESO DE COMPRA* 💳\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Por favor, envía tu *Nombre Completo*:",
        parse_mode="Markdown"
    )
    
    return PREMIUM_NAME

async def premium_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nombre del usuario"""
    context.user_data["premium_name"] = update.message.text
    
    await update.message.reply_text(
        "✅ Nombre registrado.\n\n"
        "Ahora envía tu *Teléfono Completo* (con código de país):",
        parse_mode="Markdown"
    )
    
    return PREMIUM_PHONE

async def premium_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el teléfono del usuario"""
    context.user_data["premium_phone"] = update.message.text
    
    await update.message.reply_text(
        "✅ Teléfono registrado.\n\n"
        "Por último, envía tu *Correo Electrónico*:",
        parse_mode="Markdown"
    )
    
    return PREMIUM_EMAIL

async def premium_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el email y muestra instrucciones de pago"""
    context.user_data["premium_email"] = update.message.text
    
    name = context.user_data.get("premium_name", "")
    phone = context.user_data.get("premium_phone", "")
    email = context.user_data.get("premium_email", "")
    
    keyboard = [[InlineKeyboardButton("🔙 Volver al Inicio", callback_data="back_start")]]
    
    payment_text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 *INFORMACIÓN DE PAGO* 💰\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *Tus datos registrados:*\n"
        f"👤 Nombre: {name}\n"
        f"📱 Teléfono: {phone}\n"
        f"📧 Email: {email}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💳 *INSTRUCCIONES DE PAGO:*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ *Abona $27 USD* al siguiente alias:\n"
        "```THEGITANO2AX.PF```\n\n"
        "2️⃣ *Envía el comprobante de pago* a:\n"
        "```corporatebusinessunitedstates@gmail.com```\n\n"
        "3️⃣ *Incluye en el correo:*\n"
        "   • Tu nombre completo\n"
        "   • Tu teléfono\n"
        "   • Tu email\n"
        "   • Captura del comprobante\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "⏰ *Tu cuenta será activada en menos de 24 horas*\n\n"
        "Te enviaremos tu *usuario y contraseña* vía:\n"
        "✉️ Mensaje de Telegram\n"
        "✉️ Correo Electrónico\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "¡Gracias por tu compra! 🦅\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(
        payment_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    # Log para el administrador
    logger.info(f"Nueva solicitud PREMIUM: {name} | {phone} | {email}")
    
    return ConversationHandler.END

# ================= MENÚ PREMIUM (POST-LOGIN) =================

async def show_premium_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú para usuarios PREMIUM autenticados"""
    uid = update.effective_user.id
    
    if not is_premium_user(uid):
        return await plan_premium(update, context)
    
    username = PREMIUM_USERS[uid]["username"]
    days_left = get_days_remaining(uid)
    
    keyboard = [
        [InlineKeyboardButton("📝 Texto a Voz", callback_data="premium_texto")],
        [InlineKeyboardButton("📄 Traducir Documentos", callback_data="premium_documento")],
        [InlineKeyboardButton("⚙️ Configuración", callback_data="premium_config")],
        [InlineKeyboardButton("❓ Ayuda", callback_data="premium_help")],
        [InlineKeyboardButton("🔙 Salir", callback_data="back_start")]
    ]
    
    welcome_text = (
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ *BIENVENIDO SR. {username.upper()}* ✨\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏰ Te quedan *{days_left} días* de tu licencia Premium\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎 *MENÚ PREMIUM* 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "Selecciona una opción:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    return CHOOSING_PLAN

# ================= FUNCIONES - TEXTO A VOZ =================

async def free_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prepara para recibir texto (modo FREE)"""
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    
    if not can_use_free(uid, "texto"):
        keyboard = [[InlineKeyboardButton("💎 Comprar PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text(
            "❌ *Ya usaste tu prueba FREE de esta función.*\n\n"
            "Compra PREMIUM para uso ilimitado.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return CHOOSING_PLAN
    
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = False
    
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    
    await query.edit_message_text(
        "📝 *TEXTO A VOZ*\n\n"
        "Envía el texto que deseas convertir a audio:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return CHOOSING_PLAN

async def premium_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prepara para recibir texto (modo PREMIUM)"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_text"] = True
    context.user_data["is_premium"] = True
    
    keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="premium_menu")]]
    
    await query.edit_message_text(
        "📝 *TEXTO A VOZ*\n\n"
        "Envía el texto que deseas convertir a audio:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return CHOOSING_PLAN

# ================= FUNCIONES - DOCUMENTOS =================

async def free_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prepara para recibir documento (modo FREE)"""
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    
    if not can_use_free(uid, "documento"):
        keyboard = [[InlineKeyboardButton("💎 Comprar PREMIUM", callback_data="plan_premium")]]
        await query.edit_message_text(
            "❌ *Ya usaste tu prueba FREE de esta función.*\n\n"
            "Compra PREMIUM para uso ilimitado.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return CHOOSING_PLAN
    
    context.user_data["waiting_document"] = True
    context.user_data["is_premium"] = False
    
    keyboard = [[InlineKeyboardButton("🔙 Cancelar", callback_data="plan_free")]]
    
    await query.edit_message_text(
        "📄 *TRADUCIR DOCUMENTOS*\n\n"
        "Envía un documento Word (.docx) o PDF para traducir:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return CHOOSING_PLAN

async def premium_documento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prepara para recibir documento (modo PREMIUM)"""
    query = update.callback_query
    await query.answer()
    
    context.user_data["waiting_document"] = True
    context.user_data["is_premium"] = True
    
    keyboard = [[InlineKeyboardButton("🔙 Volver al Menú", callback_data="premium_menu")]]
    
    await query.edit_message_text(
        "📄 *TRADUCIR DOCUMENTOS*\n\n"
        "Envía un documento Word (.docx) o PDF para traducir:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return CHOOSING_PLAN

# ================= HANDLERS DE CONTENIDO =================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa texto para convertir a voz"""
    uid = update.effective_user.id
    
    if not context.user_data.get("waiting_text", False):
        return
    
    try:
        processing_msg = await update.message.reply_text("⏳ Generando audio...")
        
        audio = tts(update.message.text, "es")
        
        if audio:
            await update.message.reply_voice(audio)
            
            # Marcar como usado si es FREE
            if not context.user_data.get("is_premium", False):
                mark_free_used(uid, "texto")
            
            # Verificar si ya usó todo en FREE
            if not context.user_data.get("is_premium", False) and all_free_used(uid):
                keyboard = [[InlineKeyboardButton("💎 COMPRAR PREMIUM", callback_data="plan_premium")]]
                await update.message.reply_text(
                    "━━━━━━━━━━━━━━━━━━━━━━\n"
                    "🎊 *¡ULALA!* 🎊\n"
                    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    "✅ *Ya utilizaste tu prueba FREE*\n\n"
                    "Para seguir utilizando mis servicios,\n"
                    "por favor compra la licencia PREMIUM.\n\n"
                    f"{FIRMA_TEXTO}",
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
            else:
                back_data = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
                keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=back_data)]]
                await update.message.reply_text(
                    f"✅ ¡Listo!\n\n{FIRMA_TEXTO}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        else:
            await update.message.reply_text("❌ Error al generar el audio.")
        
        await processing_msg.delete()
        context.user_data["waiting_text"] = False
        
    except Exception as e:
        logger.error(f"Error en handle_text: {e}")
        await update.message.reply_text("❌ Ocurrió un error. Intenta de nuevo.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Procesa documentos para traducción"""
    uid = update.effective_user.id
    
    if not context.user_data.get("waiting_document", False):
        return
    
    try:
        doc = update.message.document
        processing_msg = await update.message.reply_text(
            f"⏳ Procesando: {doc.file_name}..."
        )
        
        file = await context.bot.get_file(doc.file_id)
        data = await file.download_as_bytearray()
        
        if doc.file_name.endswith(".docx"):
            translated_file = translate_docx(data, "es")
            if translated_file:
                await update.message.reply_document(
                    document=translated_file,
                    filename=f"traducido_{doc.file_name}"
                )
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
                    await update.message.reply_text(
                        f"*Traducción:*\n\n{translated_text[:4000]}",
                        parse_mode="Markdown"
                    )
            else:
                await update.message.reply_text("❌ No se pudo extraer texto del PDF.")
                await processing_msg.delete()
                return
        else:
            await update.message.reply_text("❌ Formato no soportado. Solo .docx o .pdf")
            await processing_msg.delete()
            return
        
        # Marcar como usado si es FREE
        if not context.user_data.get("is_premium", False):
            mark_free_used(uid, "documento")
        
        # Verificar si ya usó todo en FREE
        if not context.user_data.get("is_premium", False) and all_free_used(uid):
            keyboard = [[InlineKeyboardButton("💎 COMPRAR PREMIUM", callback_data="plan_premium")]]
            await update.message.reply_text(
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎊 *¡ULALA!* 🎊\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ *Ya utilizaste tu prueba FREE*\n\n"
                "Para seguir utilizando mis servicios,\n"
                "por favor compra la licencia PREMIUM.\n\n"
                f"{FIRMA_TEXTO}",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            back_data = "premium_menu" if context.user_data.get("is_premium") else "plan_free"
            keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data=back_data)]]
            await update.message.reply_text(
                f"✅ ¡Documento procesado!\n\n{FIRMA_TEXTO}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        await processing_msg.delete()
        context.user_data["waiting_document"] = False
        
    except Exception as e:
        logger.error(f"Error en handle_document: {e}")
        await update.message.reply_text("❌ Ocurrió un error. Intenta de nuevo.")

# ================= CALLBACKS =================

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja todos los callbacks de botones"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "back_start":
        context.user_data.clear()
        await query.message.delete()
        await start(query, context)
    
    elif data == "plan_free":
        await plan_free(update, context)
    
    elif data == "plan_premium":
        await plan_premium(update, context)
    
    elif data == "buy_premium":
        await buy_premium(update, context)
    
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
        await query.edit_message_text(
            "⚙️ *CONFIGURACIÓN*\n\n"
            "Próximamente disponible:\n"
            "• Idioma de destino\n"
            "• Velocidad de voz\n"
            "• Formato de audio",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    elif data == "premium_help":
        keyboard = [[InlineKeyboardButton("🔙 Volver", callback_data="premium_menu")]]
        await query.edit_message_text(
            "❓ *AYUDA*\n\n"
            "*Cómo usar:*\n"
            "1️⃣ Selecciona una función\n"
            "2️⃣ Envía tu contenido\n"
            "3️⃣ Recibe el resultado\n\n"
            "*Soporte:*\n"
            "📧 corporatebusinessunitedstates@gmail.com",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

# ================= ERROR HANDLER =================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores"""
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Ocurrió un error. Usa /start para reiniciar."
        )

# ================= MAIN =================

def main():
    """Función principal"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TOKEN NO CONFIGURADO")
        return
    
    logger.info("🚀 Iniciando El Gitano Bot...")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Conversation Handler para el flujo de compra Premium
    premium_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_PLAN: [CallbackQueryHandler(button_callback)],
            PREMIUM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_name)],
            PREMIUM_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_phone)],
            PREMIUM_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, premium_email)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )
    
    app.add_handler(premium_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_error_handler(error_handler)
    
    logger.info("✅ Bot iniciado correctamente")
    logger.info("🦅 El Gitano Bot está listo")
    
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
