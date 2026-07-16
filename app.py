import os
import asyncio
from flask import Flask, send_from_directory, jsonify
from telethon import TelegramClient, events
import edge_tts
import re

# ==================== CONFIGURATION ====================
API_ID = 23963495
API_HASH = "80f834927d63945ca3a8863fba8eef49"
PHONE = "+85593883311"

# ឈ្មោះ Chat Telegram
ONLY_FROM_CHATS = []

# Keywords សម្រាប់ចាប់សារប្រាក់ចូល
RECEIVE_KEYWORDS = ["ត្រូវបានបង់ដោយ", "ទទួលបានប្រាក់", "paid by", "received"]

# Audio Settings
VOICE = "km-KH-PisethNeural"
LATEST_AUDIO_FILE = "latest_audio.mp3"

app = Flask(__name__)
client = TelegramClient("khmer_tts_session", API_ID, API_HASH)

has_new_audio = False

def khmer_number_to_words(num_str):
    khmer_digits = {'0': 'សូន្យ', '1': 'មួយ', '2': 'ពីរ', '3': 'បី', '4': 'បួន',
                    '5': 'ប្រាំ', '6': 'ប្រាំមួយ', '7': 'ប្រាំពីរ', '8': 'ប្រាំបី', '9': 'ប្រាំប្រាំបួន'}
    return "".join([khmer_digits.get(d, d) for d in str(num_str)])

def format_amount_for_speech(raw_amount: str) -> str:
    cleaned = raw_amount.replace(",", "").strip()
    if "." in cleaned:
        parts = cleaned.split(".")
        dollars = int(parts[0]) if parts[0] else 0
        cents = int(parts[1][:2]) if parts[1] else 0
        speech_parts = []
        if dollars > 0:
            speech_parts.append(f"{khmer_number_to_words(dollars)} ដុល្លារ")
        if cents > 0:
            speech_parts.append(f"{khmer_number_to_words(cents)} សេន")
        return " ".join(speech_parts) if speech_parts else "សូន្យ ដុល្លារ"
    
    num_str = cleaned.replace("$", "").replace("៛", "").strip()
    try:
        r_val = int(num_str)
        return f"{khmer_number_to_words(r_val)} រៀល"
    except ValueError:
        return f"{num_str} រៀល"

# 💡 កូដបង្កើតសំឡេងទំហំតូចខ្លាំង សម្រាប់ ESP32 (កុំឲ្យអស់ RAM)
async def generate_audio(text):
    global has_new_audio
    if os.path.exists(LATEST_AUDIO_FILE):
        try:
            os.remove(LATEST_AUDIO_FILE) # លុប File ចាស់ចោល
        except:
            pass
    communicate = edge_tts.Communicate(text, VOICE, rate="+15%", pitch="+0Hz")
    await communicate.save(LATEST_AUDIO_FILE)
    has_new_audio = True

@client.on(events.NewMessage)
async def handler(event):
    text = event.raw_text
    if not text or not text.strip():
        return
    chat = await event.get_chat()
    chat_name = getattr(chat, 'title', None) or getattr(chat, 'username', None) or ""
    if ONLY_FROM_CHATS and not any(name.lower() in chat_name.lower() for name in ONLY_FROM_CHATS):
        return
    if not any(k.lower() in text.lower() for k in RECEIVE_KEYWORDS):
        return
    
    AMOUNT_PATTERN = re.compile(r'(\d[\d,]*\.?\d*)')
    amounts = AMOUNT_PATTERN.findall(text)
    if not amounts:
        return
    amount_text = " និង ".join([format_amount_for_speech(a) for a in amounts])
    
    await generate_audio(f"ទទួលបាន {amount_text}")

@app.route('/latest-audio')
def get_latest_audio():
    global has_new_audio
    if os.path.exists(LATEST_AUDIO_FILE):
        return send_from_directory('.', LATEST_AUDIO_FILE)
    return jsonify({"status": "no audio"}), 404

async def start_telegram_async():
    await client.start(phone=PHONE)
    await client.run_until_disconnected()

def start_telegram():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_telegram_async())

import threading
threading.Thread(target=start_telegram, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
