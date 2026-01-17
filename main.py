import os
import logging
import io
import asyncio
from datetime import datetime, timedelta
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

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FIRMA = "✨ Esto fue realizado por 𝐄𝐥 𝐆𝐢𝐭𝐚𝐧𝐨 𝐓𝐫𝐚𝐝𝐮𝐜𝐜𝐢𝐨𝐧𝐞𝐬 ✨"

AVAILABLE_ACCENTS = {
    'es-es': '🇪🇸 España',
    'es-us': '🇲🇽 Latino',
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
scheduled_deletions = {}

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= UTILIDADES =================
def detect_language(text):
    try:
        return detect(text)
    except:
        return 'unknown'

def translate_text(text):
    try:
        translator = GoogleTranslator(source='auto', target='es')
        if len(text) > 4500:
            parts = [text[i:i+4500] for i in range(0, len(text), 4500)]
            return ' '.join(translator.translate(p) for p in parts)
        return translator.translate(text)
    except:
        return text

def extract_text_from_pdf(file):
    reader = PyPDF2.PdfReader(file)
    return "\n".join(page.extract_text() or "" for page in reader.pages[:20])

def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def translate_document_text(text, source_lang):
    """Traduce el texto del documento según el idioma de origen"""
    try:
        if source_lang == 'es':
            translator = GoogleTranslator(source='es', target='en')
        else:
            translator = GoogleTranslator(source='auto', target='es')
        
        if len(text) > 4500:
            parts = [text[i:i+4500] for i in range(0, len(text), 4500)]
            return ' '.join(translator.translate(p) for p in parts)
        return translator.translate(text)
    except:
        return text

def tts(text, user_id):
    accent = user_preferences.get(user_id, {}).get('accent', 'es-us')
    speed = user_preferences.get(user_id, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed]['speed']
    tts_obj = gTTS(text=text, lang=accent, slow=slow)
    audio = io.BytesIO()
    tts_obj.write_to_fp(audio)
    audio.seek(0)
    return audio

def get_main_menu_keyboard():
    """Genera el teclado del menú principal"""
    keyboard = [
        [InlineKeyboardButton("🎤 Convertir Texto a Audio", callback_data="menu_text")],
        [InlineKeyboardButton("📄 Traducir Documentos", callback_data="menu_docs")],
        [InlineKeyboardButton("🌍 Cambiar Acento", callback_data="menu_accent")],
        [InlineKeyboardButton("⚡ Velocidad de Audio", callback_data="menu_speed")],
        [InlineKeyboardButton("⚙️ Configuración", callback_data="menu_config")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_return_menu_keyboard():
    """Botón para regresar al menú principal"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Volver al Menú Principal", callback_data="return_menu")]])

async def schedule_message_deletion(context, chat_id, message_id, delay_hours=24):
    """Programa el borrado de un mensaje después de X horas"""
    await asyncio.sleep(delay_hours * 3600)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except:
        pass

# ================= COMANDOS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "╔═══════════════════════════╗\n"
        "║  🤖 𝐁𝐎𝐓 𝐓𝐑𝐀𝐃𝐔𝐂𝐓𝐎𝐑 & 𝐓𝐓𝐒  ║\n"
        "╚═══════════════════════════╝\n\n"
        "🎨 𝗠𝗶 𝗰𝗿𝗲𝗮𝗱𝗼𝗿 🦅 𝐄𝐋 𝐆𝐈𝐓𝐀𝐍𝐎 🦅\n"
        "𝗺𝗲 𝗽𝗿𝗼𝗴𝗿𝗮𝗺ó 𝗽𝗮𝗿𝗮 𝗿𝗲𝗮𝗹𝗶𝘇𝗮𝗿\n"
        "𝗲𝘀𝘁𝗼𝘀 𝘁𝗿𝗮𝗯𝗮𝗷𝗼𝘀 𝗽𝗼𝗿 𝘁𝗶:\n\n"
        "✅ Convertir texto a audio\n"
        "✅ Traducir documentos (PDF/Word)\n"
        "✅ Traducción automática\n"
        "✅ Múltiples acentos en español\n"
        "✅ Control de velocidad\n\n"
        "⚠️ Los mensajes se autodestruyen\n"
        "    en 24 horas para tu privacidad\n\n"
        "👇 Selecciona una opción:"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_main_menu_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 𝗔𝗬𝗨𝗗𝗔\n\n"
        "📝 Envía texto y lo convertiré a audio\n"
        "📄 Envía PDF/Word para traducir\n"
        "🌍 Traduzco automáticamente a español\n"
        "🎯 Todo con calidad profesional\n\n"
        f"{FIRMA}",
        reply_markup=get_return_menu_keyboard()
    )

async def accent_command(update, context):
    kb = [[InlineKeyboardButton(v, callback_data=f"accent_{k}")]
          for k, v in AVAILABLE_ACCENTS.items()]
    kb.append([InlineKeyboardButton("🏠 Menú Principal", callback_data="return_menu")])
    await update.message.reply_text(
        "🌍 Selecciona el acento para el audio:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def speed_command(update, context):
    kb = [[InlineKeyboardButton(v['name'], callback_data=f"speed_{k}")]
          for k, v in SPEED_OPTIONS.items()]
    kb.append([InlineKeyboardButton("🏠 Menú Principal", callback_data="return_menu")])
    await update.message.reply_text(
        "⚡ Selecciona la velocidad del audio:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def config_command(update, context):
    uid = update.effective_user.id
    auto = user_preferences.get(uid, {}).get('auto', False)
    kb = [
        [InlineKeyboardButton("✅ ON" if auto else "❌ OFF", callback_data="auto")],
        [InlineKeyboardButton("🏠 Menú Principal", callback_data="return_menu")]
    ]
    await update.message.reply_text(
        f"⚙️ 𝗖𝗢𝗡𝗙𝗜𝗚𝗨𝗥𝗔𝗖𝗜Ó𝗡\n\n"
        f"Traducción automática: {'✅ Activada' if auto else '❌ Desactivada'}",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= CONFIRMACIÓN DE AUTOBORRADO =================
async def ask_autodeletion_confirmation(update, context, action_type):
    """Pregunta al usuario si acepta el autoborrado de 24h"""
    kb = [
        [InlineKeyboardButton("✅ Sí, continuar", callback_data=f"confirm_{action_type}")],
        [InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_action")]
    ]
    
    await update.message.reply_text(
        "⚠️ 𝗔𝗩𝗜𝗦𝗢 𝗜𝗠𝗣𝗢𝗥𝗧𝗔𝗡𝗧𝗘\n\n"
        "Por tu seguridad y privacidad,\n"
        "este mensaje se autodestruirá\n"
        "en 24 horas.\n\n"
        "¿Deseas continuar?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# ================= BOTONES =================
async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})

    # Menú principal
    if q.data == "return_menu" or q.data == "menu_main":
        welcome_text = (
            "╔═══════════════════════════╗\n"
            "║  🤖 𝐁𝐎𝐓 𝐓𝐑𝐀𝐃𝐔𝐂𝐓𝐎𝐑 & 𝐓𝐓𝐒  ║\n"
            "╚═══════════════════════════╝\n\n"
            "👇 Selecciona una opción:"
        )
        await q.edit_message_text(welcome_text, reply_markup=get_main_menu_keyboard())
    
    # Opciones del menú
    elif q.data == "menu_text":
        await q.edit_message_text(
            "📝 𝗠𝗢𝗗𝗢 𝗧𝗘𝗫𝗧𝗢 𝗔 𝗔𝗨𝗗𝗜𝗢\n\n"
            "Envíame cualquier texto y lo\n"
            "convertiré a audio en español.\n\n"
            "Si está en otro idioma, lo\n"
            "traduciré automáticamente.",
            reply_markup=get_return_menu_keyboard()
        )
    
    elif q.data == "menu_docs":
        await q.edit_message_text(
            "📄 𝗠𝗢𝗗𝗢 𝗗𝗢𝗖𝗨𝗠𝗘𝗡𝗧𝗢𝗦\n\n"
            "Envíame un PDF o Word y\n"
            "podrás elegir:\n\n"
            "🎧 Audio traducido\n"
            "📄 Documento traducido\n\n"
            "ES ⇄ EN automáticamente",
            reply_markup=get_return_menu_keyboard()
        )
    
    elif q.data == "menu_accent":
        kb = [[InlineKeyboardButton(v, callback_data=f"accent_{k}")]
              for k, v in AVAILABLE_ACCENTS.items()]
        kb.append([InlineKeyboardButton("🏠 Menú Principal", callback_data="return_menu")])
        await q.edit_message_text(
            "🌍 Selecciona el acento:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "menu_speed":
        kb = [[InlineKeyboardButton(v['name'], callback_data=f"speed_{k}")]
              for k, v in SPEED_OPTIONS.items()]
        kb.append([InlineKeyboardButton("🏠 Menú Principal", callback_data="return_menu")])
        await q.edit_message_text(
            "⚡ Selecciona la velocidad:",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "menu_config":
        auto = user_preferences.get(uid, {}).get('auto', False)
        kb = [
            [InlineKeyboardButton("✅ ON" if auto else "❌ OFF", callback_data="auto")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="return_menu")]
        ]
        await q.edit_message_text(
            f"⚙️ 𝗖𝗢𝗡𝗙𝗜𝗚𝗨𝗥𝗔𝗖𝗜Ó𝗡\n\n"
            f"Traducción automática:\n{'✅ Activada' if auto else '❌ Desactivada'}",
            reply_markup=InlineKeyboardMarkup(kb)
        )

    # Configuraciones
    elif q.data.startswith("accent_"):
        user_preferences[uid]['accent'] = q.data.replace("accent_", "")
        await q.edit_message_text(
            f"✅ Acento cambiado correctamente\n\n{FIRMA}",
            reply_markup=get_return_menu_keyboard()
        )

    elif q.data.startswith("speed_"):
        user_preferences[uid]['speed'] = q.data.replace("speed_", "")
        await q.edit_message_text(
            f"✅ Velocidad cambiada correctamente\n\n{FIRMA}",
            reply_markup=get_return_menu_keyboard()
        )

    elif q.data == "auto":
        user_preferences[uid]['auto'] = not user_preferences[uid].get('auto', False)
        await q.edit_message_text(
            f"✅ Configuración actualizada\n\n{FIRMA}",
            reply_markup=get_return_menu_keyboard()
        )
    
    # Confirmaciones de autoborrado
    elif q.data.startswith("confirm_"):
        action = q.data.replace("confirm_", "")
        await q.edit_message_text("✅ Procesando tu solicitud...")
        
        if action == "text":
            # Procesado en handle_text
            context.user_data['confirmed'] = True
        elif action == "doc_audio":
            await process_doc_to_audio(q.message, context, uid)
        elif action == "doc_translate":
            await process_doc_translation(q.message, context, uid)
    
    elif q.data == "cancel_action":
        await q.edit_message_text(
            "❌ Acción cancelada\n\n"
            "Puedes volver cuando quieras.",
            reply_markup=get_return_menu_keyboard()
        )
    
    # Opciones de documento
    elif q.data == "doc_audio":
        kb = [
            [InlineKeyboardButton("✅ Sí, continuar", callback_data="confirm_doc_audio")],
            [InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_action")]
        ]
        await q.edit_message_text(
            "⚠️ 𝗔𝗩𝗜𝗦𝗢 𝗜𝗠𝗣𝗢𝗥𝗧𝗔𝗡𝗧𝗘\n\n"
            "Por tu seguridad y privacidad,\n"
            "este mensaje se autodestruirá\n"
            "en 24 horas.\n\n"
            "¿Deseas continuar?",
            reply_markup=InlineKeyboardMarkup(kb)
        )
    
    elif q.data == "doc_translate":
        kb = [
            [InlineKeyboardButton("✅ Sí, continuar", callback_data="confirm_doc_translate")],
            [InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_action")]
        ]
        await q.edit_message_text(
            "⚠️ 𝗔𝗩𝗜𝗦𝗢 𝗜𝗠𝗣𝗢𝗥𝗧𝗔𝗡𝗧𝗘\n\n"
            "Por tu seguridad y privacidad,\n"
            "este mensaje se autodestruirá\n"
            "en 24 horas.\n\n"
            "¿Deseas continuar?",
            reply_markup=InlineKeyboardMarkup(kb)
        )

async def process_doc_to_audio(message, context, uid):
    """Procesa documento y genera audio"""
    try:
        file_id = context.user_data.get('doc_file_id')
        file_name = context.user_data.get('doc_file_name')
        
        file = await context.bot.get_file(file_id)
        data = await file.download_as_bytearray()
        stream = io.BytesIO(data)
        
        text = extract_text_from_pdf(stream) if file_name.endswith('.pdf') else extract_text_from_docx(stream)
        
        lang = detect_language(text)
        if lang != 'es':
            text = translate_text(text)
        
        audio = tts(text, uid)
        sent_msg = await message.reply_voice(audio)
        final_msg = await message.reply_text(FIRMA, reply_markup=get_return_menu_keyboard())
        
        # Programar borrado
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, sent_msg.message_id))
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, final_msg.message_id))
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}", reply_markup=get_return_menu_keyboard())

async def process_doc_translation(message, context, uid):
    """Traduce el documento y lo reenvía"""
    try:
        file_id = context.user_data.get('doc_file_id')
        file_name = context.user_data.get('doc_file_name')
        
        file = await context.bot.get_file(file_id)
        data = await file.download_as_bytearray()
        stream = io.BytesIO(data)
        
        is_pdf = file_name.endswith('.pdf')
        text = extract_text_from_pdf(stream) if is_pdf else extract_text_from_docx(stream)
        
        lang = detect_language(text)
        translated_text = translate_document_text(text, lang)
        
        new_doc = Document()
        for paragraph in translated_text.split('\n'):
            if paragraph.strip():
                new_doc.add_paragraph(paragraph)
        
        output = io.BytesIO()
        new_doc.save(output)
        output.seek(0)
        
        lang_suffix = "EN" if lang == 'es' else "ES"
        new_filename = file_name.replace('.docx', f'_traducido_{lang_suffix}.docx').replace('.pdf', f'_traducido_{lang_suffix}.docx')
        
        sent_msg = await message.reply_document(document=output, filename=new_filename)
        final_msg = await message.reply_text(FIRMA, reply_markup=get_return_menu_keyboard())
        
        # Programar borrado
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, sent_msg.message_id))
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, final_msg.message_id))
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}", reply_markup=get_return_menu_keyboard())

# ================= MENSAJES =================
async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text
    
    # Preguntar por autoborrado
    kb = [
        [InlineKeyboardButton("✅ Sí, continuar", callback_data="confirm_text_process")],
        [InlineKeyboardButton("❌ No, cancelar", callback_data="cancel_action")]
    ]
    
    # Guardar el texto para procesarlo después
    context.user_data['pending_text'] = text
    
    await update.message.reply_text(
        "⚠️ 𝗔𝗩𝗜𝗦𝗢 𝗜𝗠𝗣𝗢𝗥𝗧𝗔𝗡𝗧𝗘\n\n"
        "Por tu seguridad y privacidad,\n"
        "este mensaje se autodestruirá\n"
        "en 24 horas.\n\n"
        "¿Deseas continuar?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def process_text_confirmed(message, context, uid):
    """Procesa el texto después de confirmar"""
    text = context.user_data.get('pending_text', '')
    
    if detect_language(text) != 'es':
        text = translate_text(text)
    
    audio = tts(text, uid)
    sent_msg = await message.reply_voice(audio)
    final_msg = await message.reply_text(FIRMA, reply_markup=get_return_menu_keyboard())
    
    # Programar borrado en 24 horas
    asyncio.create_task(schedule_message_deletion(context, message.chat_id, sent_msg.message_id))
    asyncio.create_task(schedule_message_deletion(context, message.chat_id, final_msg.message_id))

async def handle_doc(update, context):
    doc = update.message.document
    uid = update.effective_user.id
    
    context.user_data['doc_file_id'] = doc.file_id
    context.user_data['doc_file_name'] = doc.file_name
    
    kb = [
        [InlineKeyboardButton("🎧 Audio traducido", callback_data="doc_audio")],
        [InlineKeyboardButton("📄 Documento traducido", callback_data="doc_translate")],
        [InlineKeyboardButton("🏠 Menú Principal", callback_data="return_menu")]
    ]
    
    await update.message.reply_text(
        "📄 𝗗𝗢𝗖𝗨𝗠𝗘𝗡𝗧𝗢 𝗥𝗘𝗖𝗜𝗕𝗜𝗗𝗢\n\n"
        "¿Qué deseas hacer?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

# Actualizar el handler de botones para procesar texto
async def buttons(update, context):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    user_preferences.setdefault(uid, {})

    # ... (código anterior de botones) ...
    
    # Agregar este caso para confirmar procesamiento de texto
    if q.data == "confirm_text_process":
        await q.edit_message_text("✅ Procesando tu texto...")
        await process_text_confirmed(q.message, context, uid)

# ================= MAIN =================
def main():
    if not TELEGRAM_BOT_TOKEN:
        print("❌ TOKEN NO CONFIGURADO")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("accent", accent_command))
    app.add_handler(CommandHandler("speed", speed_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))

    print("🤖 Bot iniciado correctamente")
    app.run_polling()

if __name__ == "__main__":
    main()
