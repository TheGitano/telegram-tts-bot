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
import whisper

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIRMA_TEXTO = "¡¡ Esto fue realizado por 🦅𝓣𝓽ͭ𝓱ͪ𝓮ͤ𝓖𝓲𝓽ͭ𝓪ͣ𝓷𝓸 🦅 !!"

AUTHORIZED_USERS = {"Gitano": "8376"}  # Usuario permanente
trial_limits = 1

model = whisper.load_model("base")
user_sessions = {}  # {telegram_id: {"username": str, "authenticated": bool, "premium": bool, "first_use": datetime}}
user_trials = {}    # {telegram_id: {"texto": int, "audio": int, "documento": int}}

# ================= LOGGING =================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================= UTILIDADES =================

def translate_text(text, target="es"):
    translator = GoogleTranslator(source="auto", target=target)
    return translator.translate(text)

def detect_language(text):
    try:
        return detect(text)
    except:
        return "unknown"

def tts(text, lang="es"):
    audio = io.BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(audio)
    audio.seek(0)
    return audio

def extract_text_from_pdf(file_bytes):
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)

def translate_docx(file_bytes, target="es"):
    doc = Document(io.BytesIO(file_bytes))
    for p in doc.paragraphs:
        p.text = translate_text(p.text, target)
    out_stream = io.BytesIO()
    doc.save(out_stream)
    out_stream.seek(0)
    return out_stream

def convert_ogg_to_wav(ogg_path, wav_path):
    subprocess.run(["ffmpeg", "-y", "-i", ogg_path, wav_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def transcribe_audio(path):
    result = model.transcribe(path)
    return result["text"]

def check_trial(uid, function_name):
    user_trials.setdefault(uid, {"texto": 0, "audio": 0, "documento": 0})
    if user_sessions[uid]["premium"]:
        return True
    if user_trials[uid][function_name] >= trial_limits:
        return False
    user_trials[uid][function_name] += 1
    return True

def check_expiration(uid):
    session = user_sessions.get(uid)
    if not session:
        return False
    if session["premium"]:
        return True
    if session["username"] == "Gitano":
        return True
    if datetime.now() > session["first_use"] + timedelta(days=30):
        return False
    return True

# ================= MENÚ PRINCIPAL =================

async def show_main_menu(update, context):
    uid = update.effective_user.id
    if not user_sessions.get(uid, {}).get("authenticated", False):
        await update.message.reply_text("🔑 Debes iniciar sesión con tu usuario y contraseña usando /start")
        return

    kb = [
        [InlineKeyboardButton("🎧 Conversación bilingüe (Intérprete)", callback_data="menu_interpreter")],
        [InlineKeyboardButton("🗣 Traductor de voz", callback_data="menu_voice_translator")],
        [InlineKeyboardButton("📄 Traducir documentos", callback_data="menu_docs")],
        [InlineKeyboardButton("📝 Texto a voz", callback_data="menu_text")],
        [InlineKeyboardButton("🧪 Prueba (trial limitado)", callback_data="menu_trial")],
        [InlineKeyboardButton("💎 Versión Premium", callback_data="menu_premium")],
        [InlineKeyboardButton("⚙ Configuración", callback_data="menu_config")],
        [InlineKeyboardButton("❓ Ayuda", callback_data="menu_help")]
    ]

    username = user_sessions[uid]["username"]
    text = f"🎙 Bienvenido {username}!\nEste bot ha sido creado por *El Gitano* para ayudarte a:\n"\
           "• Traducir texto a español latino\n"\
           "• Traducir audios (Inglés ⇄ Español)\n"\
           "• Traducir documentos Word/PDF\n"\
           "• Conversar en modo intérprete bilingüe\n"\
           "• Convertir texto a voz con acento latino\n\nSelecciona una opción:"

    if update.message:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# ================= LOGIN =================

async def start(update, context):
    uid = update.effective_user.id
    user_sessions.setdefault(uid, {"authenticated": False, "premium": False})
    await update.message.reply_text("🔑 Ingresa tu usuario:")
    return "USERNAME"

async def login_username(update, context):
    context.user_data["username_attempt"] = update.message.text
    await update.message.reply_text("🔑 Ingresa tu contraseña:")
    return "PASSWORD"

async def login_password(update, context):
    uid = update.effective_user.id
    username = context.user_data.get("username_attempt")
    password = update.message.text

    if (username in AUTHORIZED_USERS and AUTHORIZED_USERS[username] == password) or (username=="Gitano" and password=="8376"):
        user_sessions[uid] = {"username": username, "authenticated": True, "premium": username=="Gitano", "first_use": datetime.now()}
        await update.message.reply_text(f"🎉 ¡¡Bienvenido {username}!! 🎉\nYa estás autenticado y puedes usar el bot.")
        await show_main_menu(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text("❌ Usuario o contraseña incorrecta. Intenta de nuevo.")
        return await start(update, context)

# ================= BOTONES =================

async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_sessions.setdefault(uid, {"authenticated": False, "premium": False, "first_use": datetime.now()})
    if not user_sessions[uid]["authenticated"]:
        await update.callback_query.edit_message_text("❌ Debes iniciar sesión primero con /start")
        return

    if q.data == "menu_interpreter":
        await q.edit_message_text("🎧 Modo intérprete activado. Envíame audio para traducir.")
    elif q.data == "menu_voice_translator":
        await q.edit_message_text("🗣 Envíame un audio para traducir (Inglés ⇄ Español).")
    elif q.data == "menu_docs":
        await q.edit_message_text("📄 Envíame un documento Word o PDF para traducirlo.")
    elif q.data == "menu_text":
        await q.edit_message_text("📝 Envíame texto para convertir a voz.")
    elif q.data == "menu_trial":
        await q.edit_message_text("🧪 Has seleccionado la prueba. Solo un uso por función. Después deberás comprar Premium.")
    elif q.data == "menu_premium":
        kb = [[InlineKeyboardButton("💰 PAGAR", callback_data="pay")], [InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
        text = ("💎 *Versión Premium*\n\n"
                "Acceso ilimitado a todas las funciones.\n"
                "Costo: $27 dólares por 30 días.\n\n"
                "Para abonar, presiona PAGAR y completa tu información.")
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
    elif q.data == "pay":
        await q.edit_message_text("💳 Ingresa tu nombre completo, correo y teléfono separados por comas.\nAlias de pago: THEGITANO2AX.PF\nEnvía la captura de pago a corporatebusinessunitedstates@gmail.com")
    elif q.data == "back_menu":
        await show_main_menu(update, context)

# ================= TEXTO =================

async def handle_text(update, context):
    uid = update.effective_user.id
    if not check_expiration(uid):
        await update.message.reply_text("❌ Tu versión trial caducó. Debes comprar Premium.")
        return
    if not check_trial(uid, "texto"):
        await update.message.reply_text("¡¡ Ulala, veo que ya me utilizaste y probaste mi funcionamiento pero para seguir usandome debes comprar la versión premium !!!")
        return
    audio = tts(update.message.text, "es")
    await update.message.reply_voice(audio)
    kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
    await update.message.reply_text(FIRMA_TEXTO, reply_markup=InlineKeyboardMarkup(kb))

# ================= DOCUMENTOS =================

async def handle_doc(update, context):
    uid = update.effective_user.id
    if not check_expiration(uid):
        await update.message.reply_text("❌ Tu versión trial caducó. Debes comprar Premium.")
        return
    if not check_trial(uid, "documento"):
        await update.message.reply_text("¡¡ Ulala, veo que ya me utilizaste y probaste mi funcionamiento pero para seguir usandome debes comprar la versión premium !!!")
        return
    doc = update.message.document
    file = await context.bot.get_file(doc.file_id)
    data = await file.download_as_bytearray()

    if doc.file_name.endswith(".docx"):
        translated_file = translate_docx(data, "es")
        await update.message.reply_document(document=translated_file, filename=f"traducido_{doc.file_name}")
    else:
        text = extract_text_from_pdf(data)
        translated_text = translate_text(text, "es")
        audio = tts(translated_text, "es")
        await update.message.reply_voice(audio)

    kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
    await update.message.reply_text(FIRMA_TEXTO, reply_markup=InlineKeyboardMarkup(kb))

# ================= AUDIO =================

async def handle_voice(update, context):
    uid = update.effective_user.id
    if not check_expiration(uid):
        await update.message.reply_text("❌ Tu versión trial caducó. Debes comprar Premium.")
        return
    if not check_trial(uid, "audio"):
        await update.message.reply_text("¡¡ Ulala, veo que ya me utilizaste y probaste mi funcionamiento pero para seguir usandome debes comprar la versión premium !!!")
        return

    voice = update.message.voice
    file = await context.bot.get_file(voice.file_id)
    ogg_path = f"/tmp/{voice.file_id}.ogg"
    wav_path = f"/tmp/{voice.file_id}.wav"
    await file.download_to_drive(ogg_path)
    convert_ogg_to_wav(ogg_path, wav_path)

    text = transcribe_audio(wav_path)
    lang = detect_language(text)

    if lang == "en" or user_sessions[uid]["premium"]:
        translated = translate_text(text, "es")
        audio = tts(translated, "es")
    else:
        audio = tts(text, "es")

    await update.message.reply_voice(audio)
    kb = [[InlineKeyboardButton("⬅ Volver al menú", callback_data="back_menu")]]
    await update.message.reply_text(FIRMA_TEXTO, reply_markup=InlineKeyboardMarkup(kb))

# ================= MAIN =================

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("TOKEN NO CONFIGURADO")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            "USERNAME": [MessageHandler(filters.TEXT & ~filters.COMMAND, login_username)],
            "PASSWORD": [MessageHandler(filters.TEXT & ~filters.COMMAND, login_password)]
        },
        fallbacks=[]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))

    app.run_polling()

if __name__ == "__main__":
    main()
