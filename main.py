import os
import logging
import io
import asyncio
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
import speech_recognition as sr
from pydub import AudioSegment

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

# ================= LOGGING =================
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= UTILIDADES =================
def detect_language(text):
    try:
        lang = detect(text)
        return lang
    except:
        return 'unknown'

def translate_text(text, target='es'):
    try:
        translator = GoogleTranslator(source='auto', target=target)
        if len(text) > 4500:
            parts = [text[i:i+4500] for i in range(0, len(text), 4500)]
            return ' '.join(translator.translate(p) for p in parts)
        return translator.translate(text)
    except Exception as e:
        logger.error(f"Error traduciendo: {e}")
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

def tts(text, user_id, force_lang=None):
    """Genera audio TTS en el idioma especificado"""
    if force_lang:
        lang = force_lang
    else:
        accent = user_preferences.get(user_id, {}).get('accent', 'es-us')
        lang = accent
    
    speed = user_preferences.get(user_id, {}).get('speed', 'normal')
    slow = SPEED_OPTIONS[speed]['speed']
    
    try:
        tts_obj = gTTS(text=text, lang=lang, slow=slow)
        audio = io.BytesIO()
        tts_obj.write_to_fp(audio)
        audio.seek(0)
        return audio
    except Exception as e:
        logger.error(f"Error en TTS: {e}")
        # Fallback a inglés o español
        fallback_lang = 'es' if 'es' in str(lang) else 'en'
        tts_obj = gTTS(text=text, lang=fallback_lang, slow=slow)
        audio = io.BytesIO()
        tts_obj.write_to_fp(audio)
        audio.seek(0)
        return audio

async def transcribe_audio(file_path):
    """Transcribe audio a texto usando speech_recognition"""
    try:
        recognizer = sr.Recognizer()
        
        # Convertir a WAV si es necesario
        audio = AudioSegment.from_file(file_path)
        wav_path = file_path.replace('.oga', '.wav').replace('.ogg', '.wav')
        audio.export(wav_path, format='wav')
        
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            
            # Intentar reconocer en español primero
            try:
                text_es = recognizer.recognize_google(audio_data, language='es-ES')
                return text_es, 'es'
            except:
                # Si falla, intentar en inglés
                try:
                    text_en = recognizer.recognize_google(audio_data, language='en-US')
                    return text_en, 'en'
                except:
                    return None, None
    except Exception as e:
        logger.error(f"Error transcribiendo audio: {e}")
        return None, None

def get_main_menu_keyboard():
    """Genera el teclado del menú principal"""
    keyboard = [
        [InlineKeyboardButton("🎤 Convertir Texto a Audio", callback_data="menu_text")],
        [InlineKeyboardButton("🎙️ Traducir Audio", callback_data="menu_audio")],
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
        "✅ Traducir audio (voz a voz)\n"
        "✅ Traducir documentos (PDF/Word)\n"
        "✅ Traducción automática ES ⇄ EN\n"
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
        "📝 Envía texto para convertir a audio\n"
        "🎙️ Envía audio de voz para traducir\n"
        "📄 Envía PDF/Word para traducir\n"
        "🌍 Traduzco automáticamente ES ⇄ EN\n"
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

# ================= PROCESAMIENTO =================
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
            text = translate_text(text, 'es')
        
        audio = tts(text, uid)
        sent_msg = await message.reply_voice(audio)
        final_msg = await message.reply_text(FIRMA, reply_markup=get_return_menu_keyboard())
        
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
        
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, sent_msg.message_id))
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, final_msg.message_id))
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}", reply_markup=get_return_menu_keyboard())

async def process_text_audio(message, context, uid, translate=False):
    """Procesa el texto y genera audio (original o traducido)"""
    try:
        text = context.user_data.get('pending_text', '')
        original_lang = context.user_data.get('text_lang', 'es')
        
        if translate:
            # Traducir el texto
            if original_lang == 'es':
                text = translate_text(text, 'en')
                audio_lang = 'en'
            else:
                text = translate_text(text, 'es')
                audio_lang = user_preferences.get(uid, {}).get('accent', 'es-us')
        else:
            # Audio en idioma original
            audio_lang = 'en' if original_lang == 'en' else user_preferences.get(uid, {}).get('accent', 'es-us')
        
        audio = tts(text, uid, force_lang=audio_lang)
        sent_msg = await message.reply_voice(audio)
        final_msg = await message.reply_text(FIRMA, reply_markup=get_return_menu_keyboard())
        
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, sent_msg.message_id))
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, final_msg.message_id))
        
    except Exception as e:
        await message.reply_text(f"❌ Error: {str(e)}", reply_markup=get_return_menu_keyboard())

async def process_voice_translation(message, context, uid):
    """Procesa audio de voz y lo traduce"""
    try:
        status_msg = await message.reply_text("🎙️ Transcribiendo audio...")
        
        voice_file_id = context.user_data.get('voice_file_id')
        file = await context.bot.get_file(voice_file_id)
        
        # Descargar archivo
        file_path = f"voice_{uid}.oga"
        await file.download_to_drive(file_path)
        
        # Transcribir
        text, detected_lang = await transcribe_audio(file_path)
        
        if not text:
            await status_msg.edit_text("❌ No pude transcribir el audio. Intenta hablar más claro.")
            return
        
        # Traducir automáticamente
        if detected_lang == 'es':
            translated_text = translate_text(text, 'en')
            target_lang = 'en'
            lang_name = "inglés"
        else:
            translated_text = translate_text(text, 'es')
            target_lang = user_preferences.get(uid, {}).get('accent', 'es-us')
            lang_name = "español"
        
        await status_msg.edit_text(f"✅ Transcrito: {text}\n\n🔄 Traduciendo a {lang_name}...")
        
        # Generar audio traducido
        audio = tts(translated_text, uid, force_lang=target_lang)
        
        await status_msg.delete()
        sent_msg = await message.reply_voice(audio, caption=f"📝 Original: {text}\n🌍 Traducido: {translated_text}")
        final_msg = await message.reply_text(FIRMA, reply_markup=get_return_menu_keyboard())
        
        # Limpiar archivo temporal
        try:
            os.remove(file_path)
            os.remove(file_path.replace('.oga', '.wav'))
        except:
            pass
        
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, sent_msg.message_id))
        asyncio.create_task(schedule_message_deletion(context, message.chat_id, final_msg.message_id))
        
    except Exception as e:
        await message.reply_text(f"❌ Error procesando audio: {str(e)}", reply_markup=get_return_menu_keyboard())

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
            "Envíame texto en español o inglés.\n"
            "Te preguntaré si quieres el audio\n"
            "en el idioma original o traducido.",
            reply_markup=get_return_menu_keyboard()
        )
    
    elif q.data == "menu_audio":
        await q.edit_message_text(
            "🎙️ 𝗠𝗢𝗗𝗢 𝗧𝗥𝗔𝗗𝗨𝗖𝗧𝗢𝗥 𝗗𝗘 𝗩𝗢𝗭\n\n"
            "Envíame un audio de voz y lo\n"
            "traduciré automáticamente:\n\n"
            "🇪🇸 Español → 🇬🇧 Inglés\n"
            "🇬🇧 Inglés → 🇪🇸 Español\n\n"
            "Recibirás el audio traducido.",
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
    
    # Opciones de idioma para texto
    elif q.data == "text_original":
        await q.edit_message_text("✅ Procesando en idioma original...")
        await process_text_audio(q.message, context, uid, translate=False)
    
    elif q.data == "text_translated":
        await q.edit_message_text("✅ Procesando y traduciendo...")
        await process_text_audio(q.message, context, uid, translate=True)
    
    # Confirmación de audio de voz
    elif q.data == "confirm_voice_process":
        await q.edit_message_text("✅ Procesando tu audio...")
        await process_voice_translation(q.message, context, uid)
    
    # Confirmaciones de documento
    elif q.data == "confirm_doc_audio":
        await q.edit_message_text("✅ Procesando documento para audio...")
        await process_doc_to_audio(q.message, context, uid)
    
    elif q.data == "confirm_doc_translate":
        await q.edit_message_text("✅ Traduciendo documento...")
        await process_doc_translation(q.message, context, uid)
    
    elif q.data == "cancel_action":
        await q.edit_message_text(
            "❌ Acción cancelada\n\n"
            "Puedes volver cuando quieras.",
            reply_markup=get_return_menu_keyboard()
        )
    
    # Opciones de documento (mostrar confirmación de 24h)
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

# ================= MENSAJES =================
async def handle_text(update, context):
    uid = update.effective_user.id
    text = update.message.text
    
    # Detectar idioma
    lang = detect_language(text)
    
    # Guardar datos
    context.user_data['pending_text'] = text
    context.user_data['text_lang'] = lang
    
    # Solo procesar inglés y español
    if lang not in ['en', 'es']:
        await update.message.reply_text(
            "❌ Solo puedo procesar texto en inglés o español.",
            reply_markup=get_return_menu_keyboard()
        )
        return
    
    lang_name = "inglés" if lang == 'en' else "español"
    target_lang = "español" if lang == 'en' else "inglés"
    
    # Preguntar qué tipo de audio quiere
    kb = [
        [InlineKeyboardButton(f"🎵 Audio en {lang_name} (original)", callback_data="text_original")],
        [InlineKeyboardButton(f"🌍 Audio traducido a {target_lang}", callback_data="text_translated")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="cancel_action")]
    ]
    
    await update.message.reply_text(
        f"📝 Texto detectado en {lang_name}\n\n"
        "⚠️ El audio se autodestruirá en 24h\n\n"
        "¿Qué tipo de audio deseas?",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def handle_voice(update, context):
    """Maneja mensajes de voz"""
    uid = update.effective_user.id
    
    # Guardar ID del archivo de voz
    context.user_data['voice_file_id'] = update.message.voice.file_id
    
    # Preguntar confirmación
    kb = [
