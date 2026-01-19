import os
import io
import logging
import subprocess
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

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIRMA_TEXTO = "¡¡ Esto fue realizado por 🦅𝓣𝓱𝓮𝓖𝓲𝓽𝓪𝓷𝓸 🦅 !!"

AUTHORIZED_USERS = {"Gitano": "8376"}
trial_limits = 1

user_sessions = {}
user_trials = {}

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= UTILIDADES =================

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

def detect_language(text):
    """Detecta el idioma del texto"""
    try:
        return detect(text)
    except:
        return "unknown"

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
    """Extrae texto de PDF con manejo de errores"""
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

def check_trial(uid, function_name):
    """Verifica si el usuario puede usar la función en modo trial"""
    user_trials.setdefault(uid, {"texto": 0, "documento": 0})
    
    if uid not in user_sessions:
        return False
    
    if user_sessions[uid].get("premium", False):
        return True
    
    if user_trials[uid][function_name] >= trial_limits:
        return False
    
    user_trials[uid][function_name] += 1
    return True

def check_expiration(uid):
    """Verifica si la sesión del usuario sigue válida"""
    session = user_sessions.get(uid)
    if not session:
        return False
    
    if session.get("premium", False):
        return True
    
    if session.get("username") == "Gitano":
        return True
    
    first_use = session.get("first_use")
    if first_use and datetime.now() > first_use + timedelta(days=30):
        return False
    
    return True

# ================= LOGIN =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de login"""
    uid = update.effective_user.id
    user_sessions.setdefault(uid, {"authenticated": False, "premium": False})
    
    await update.message.reply_text(
        "🔐 *Bienvenido a El Gitano Bot*\n\n"
        "Por favor, ingresa tu usuario:",
        parse_mode="Markdown"
    )
    return "USERNAME"

async def login_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el ingreso del username"""
    context.user_data["username_attempt"] = update.message.text.strip()
    await update.message.reply_text("🔑 Ahora ingresa tu contraseña:")
    return "PASSWORD"

async def login_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Valida las credenciales"""
    uid = update.effective_user.id
    username = context.user_data.get("username_attempt", "")
    password = update.message.text.strip()

    is_valid = (
        (username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password) or
        (username == "Gitano" and password == "8376")
    )

    if is_valid:
        user_sessions[uid] = {
            "username": username,
            "authenticated": True,
            "premium": username == "Gitano",
            "first_use": datetime.now()
        }
        
        await update.message.reply_text(
            f"🎉 *¡Bienvenido {username}!* 🎉\n\n"
            f"Ya estás autenticado y puedes usar el bot.\n"
            f"Tipo de cuenta: {'Premium' if username == 'Gitano' else 'Trial'}",
            parse_mode="Markdown"
        )
        
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ Usuario o contraseña incorrecta.\n"
            "Intenta de nuevo con /start"
        )
        return ConversationHandler.END

# ================= MENÚ =================

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú principal"""
    uid = update.effective_user.id
    
    if not user_sessions.get(uid, {}).get("authenticated", False):
        message_text = "🔒 Debes iniciar sesión primero con /start"
        if update.message:
            await update.message.reply_text(message_text)
        else:
            await update.callback_query.message.reply_text(message_text)
        return

    kb = [
        [InlineKeyboardButton("📄 Traducir documentos", callback_data="menu_docs")],
        [InlineKeyboardButton("📝 Texto a voz", callback_data="menu_text")],
        [InlineKeyboardButton("🧪 Prueba (trial limitado)", callback_data="menu_trial")],
        [InlineKeyboardButton("💎 Versión Premium", callback_data="menu_premium")],
        [InlineKeyboardButton("⚙ Configuración", callback_data="menu_config")],
        [InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")]
    ]

    username = user_sessions[uid]["username"]
    is_premium = user_sessions[uid].get("premium", False)
    account_type = "Premium ⭐" if is_premium else "Trial 🧪"
    
    text = (
        f"🎙 *Bienvenido {username}!*\n"
        f"Tipo de cuenta: {account_type}\n\n"
        f"Este bot ha sido creado por *El Gitano* para ayudarte a:\n"
        f"• Traducir texto a español latino\n"
        f"• Traducir documentos Word/PDF\n"
        f"• Convertir texto a voz con acento latino\n\n"
        f"Selecciona una opción:"
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )

# ================= BOTONES =================

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los callbacks de los botones"""
    q = update.callback_query
    await q.answer()
    
    uid = update.effective_user.id
    
    if not user_sessions.get(uid, {}).get("authenticated", False):
        await q.edit_message_text("❌ Debes iniciar sesión primero con /start")
        return

    data = q.data
    
    if data == "menu_docs":
        await q.edit_message_text(
            "📄 *Traductor de documentos*\n\n"
            "Envíame un documento Word (.docx) o PDF para traducirlo al español.",
            parse_mode="Markdown"
        )
    
    elif data == "menu_text":
        await q.edit_message_text(
            "📝 *Texto a voz*\n\n"
            "Envíame cualquier texto y lo convertiré a audio con voz en español latino.",
            parse_mode="Markdown"
        )
    
    elif data == "menu_trial":
        trials_used = user_trials.get(uid, {"texto": 0, "documento": 0})
        await q.edit_message_text(
            f"🧪 *Modo Trial*\n\n"
            f"Tienes {trial_limits} uso por función.\n\n"
            f"Usos realizados:\n"
            f"• Texto a voz: {trials_used['texto']}/{trial_limits}\n"
            f"• Traductor de documentos: {trials_used['documento']}/{trial_limits}\n\n"
            f"Después deberás comprar Premium para uso ilimitado.",
            parse_mode="Markdown"
        )
    
    elif data == "menu_premium":
        kb = [
            [InlineKeyboardButton("💰 PAGAR", callback_data="pay")],
            [InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]
        ]
        text = (
            "💎 *Versión Premium*\n\n"
            "✨ Acceso ilimitado a todas las funciones\n"
            "✨ Sin restricciones de uso\n"
            "✨ Soporte prioritario\n\n"
            "💵 Costo: $27 USD por 30 días\n\n"
            "Para adquirir Premium, presiona el botón PAGAR."
        )
        await q.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    
    elif data == "pay":
        await q.edit_message_text(
            "💳 *Información de Pago*\n\n"
            "Alias de pago: `THEGITANO2AX.PF`\n\n"
            "Después de realizar el pago:\n"
            "1. Toma una captura de pantalla del comprobante\n"
            "2. Envíala a: corporatebusinessunitedstates@gmail.com\n"
            "3. Incluye tu nombre completo, correo y teléfono\n\n"
            "Tu cuenta será activada en menos de 24 horas.",
            parse_mode="Markdown"
        )
    
    elif data == "menu_config":
        await q.edit_message_text(
            "⚙ *Configuración*\n\n"
            "Próximamente podrás configurar:\n"
            "• Idioma de destino preferido\n"
            "• Velocidad de voz\n"
            "• Formato de audio\n\n"
            "Esta función estará disponible pronto.",
            parse_mode="Markdown"
        )
    
    elif data == "menu_help":
        kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
        await q.edit_message_text(
            "❓ *Ayuda*\n\n"
            "*Cómo usar el bot:*\n\n"
            "1️⃣ Selecciona una función del menú principal\n"
            "2️⃣ Envía el contenido a traducir/convertir\n"
            "3️⃣ Espera la respuesta del bot\n\n"
            "*Funciones disponibles:*\n"
            "• *Texto a voz:* Envía texto para convertirlo a audio\n"
            "• *Documentos:* Envía Word o PDF para traducir\n\n"
            "Para soporte contacta: corporatebusinessunitedstates@gmail.com",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode="Markdown"
        )
    
    elif data == "back_menu":
        await show_main_menu(update, context)

# ================= FUNCIONES =================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto para convertir a voz"""
    uid = update.effective_user.id
    
    if uid not in user_sessions or not user_sessions[uid].get("authenticated"):
        await update.message.reply_text("🔒 Debes iniciar sesión primero con /start")
        return
    
    if not check_expiration(uid):
        await update.message.reply_text(
            "❌ Tu versión trial caducó.\n"
            "Debes comprar Premium para continuar usando el bot."
        )
        return
    
    if not check_trial(uid, "texto"):
        kb = [[InlineKeyboardButton("💎 Ver Premium", callback_data="menu_premium")]]
        await update.message.reply_text(
            "🚫 Ya usaste tu prueba gratuita de esta función.\n"
            "Compra Premium para uso ilimitado.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    
    try:
        processing_msg = await update.message.reply_text("⏳ Generando audio...")
        
        audio = tts(update.message.text, "es")
        
        if audio:
            await update.message.reply_voice(audio)
            kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
            await update.message.reply_text(
                FIRMA_TEXTO,
                reply_markup=InlineKeyboardMarkup(kb)
            )
        else:
            await update.message.reply_text(
                "❌ Error al generar el audio. Intenta de nuevo."
            )
        
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error en handle_text: {e}")
        await update.message.reply_text(
            "❌ Ocurrió un error al procesar tu solicitud. Intenta de nuevo."
        )

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja documentos para traducción"""
    uid = update.effective_user.id
    
    if uid not in user_sessions or not user_sessions[uid].get("authenticated"):
        await update.message.reply_text("🔒 Debes iniciar sesión primero con /start")
        return
    
    if not check_expiration(uid):
        await update.message.reply_text(
            "❌ Tu versión trial caducó.\n"
            "Debes comprar Premium para continuar usando el bot."
        )
        return
    
    if not check_trial(uid, "documento"):
        kb = [[InlineKeyboardButton("💎 Ver Premium", callback_data="menu_premium")]]
        await update.message.reply_text(
            "🚫 Ya usaste tu prueba gratuita de esta función.\n"
            "Compra Premium para uso ilimitado.",
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return
    
    try:
        doc = update.message.document
        processing_msg = await update.message.reply_text(
            f"⏳ Procesando documento: {doc.file_name}..."
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
                await update.message.reply_text(
                    "❌ Error al traducir el documento Word."
                )
        
        elif doc.file_name.endswith(".pdf"):
            text = extract_text_from_pdf(data)
            if text:
                translated_text = translate_text(text, "es")
                audio = tts(translated_text, "es")
                if audio:
                    await update.message.reply_voice(audio)
                else:
                    await update.message.reply_text(
                        f"*Traducción del PDF:*\n\n{translated_text[:4000]}",
                        parse_mode="Markdown"
                    )
            else:
                await update.message.reply_text(
                    "❌ No se pudo extraer texto del PDF."
                )
        else:
            await update.message.reply_text(
                "❌ Formato no soportado. Envía archivos .docx o .pdf"
            )
            await processing_msg.delete()
            return

        kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
        await update.message.reply_text(
            FIRMA_TEXTO,
            reply_markup=InlineKeyboardMarkup(kb)
        )
        await processing_msg.delete()
        
    except Exception as e:
        logger.error(f"Error en handle_doc: {e}")
        await update.message.reply_text(
            "❌ Ocurrió un error al procesar el documento."
        )

# ================= ERROR HANDLER =================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja errores globales"""
    logger.error(f"Error: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ Ocurrió un error inesperado. Por favor intenta de nuevo."
        )

# ================= MAIN =================

def main():
    """Función principal"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TOKEN NO CONFIGURADO. Define TELEGRAM_BOT_TOKEN en las variables de entorno.")
        return

    logger.info("🚀 Iniciando bot...")
    
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            "USERNAME": [MessageHandler(filters.TEXT & ~filters.COMMAND, login_username)],
            "PASSWORD": [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)]
        },
        fallbacks=[CommandHandler('start', start)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_error_handler(error_handler)

    logger.info("✅ Bot iniciado correctamente")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
