import os
import re
import asyncio
from flask import Flask, send_from_directory, jsonify
from telethon import TelegramClient, events
import edge_tts

app = Flask(__name__)

# ==================== កែព័ត៌មាន Telegram របស់បងនៅទីនេះ ====================
API_ID = 36651859
API_HASH = "d919ac5b434f50e6b2d447060a6af7de"
PHONE = "+85587671641"
ONLY_FROM_CHATS = ["Exchange KHR", "Meng and Kon Pov"]
RECEIVE_KEYWORDS = ["ត្រូវបានបង់ដោយ", "ទទួលបានប្រាក់", "paid by", "received"]
VOICE = "km-KH-PisethNeural" # សំឡេង AI ធម្មជាតិ

AMOUNT_PATTERN = re.compile(
    r'(\$\s?[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s?\$|៛\s?[\d,]+|[\d,]+\s?៛|\.\d+\s?\$|\$\s?\.\d+|\b\d+\.\d+\b|\.\d+)'
)
# =========================================================================

LATEST_AUDIO_FILE = "latest.mp3"
has_new_audio = False

def khmer_number_to_words(num: int) -> str:
    if num == 0: return ""
    digits = ["", "មួយ", "ពីរ", "បី", "បួន", "ប្រាំ", "ប្រាំ មួយ", "ប្រាំ ពីរ", "ប្រាំ បី", "ប្រាំ បួន"]
    tens = ["", "ដប់", "ម្ភៃ", "សាម ស៊ិប", "សែ ស៊ិប", "ហា ស៊ិប", "ហុក ស៊ិប", "ចិត្ត ស៊ិប", "ប៉ែត ស៊ិប", "កៅ ស៊ិប"]
    if num < 10: return digits[num]
    if num < 100:
        ten_digit = num // 10
        remainder = num % 10
        if remainder == 0: return tens[ten_digit]
        return f"{tens[ten_digit]} {digits[remainder]}"
    units = [(1000000000, "ប៊ី លី យ៉ុន"), (100000000, "រយ លាន"), (10000000, "ដប់ លាន"), 
             (1000000, "លាន"), (100000, "សែន"), (10000, "ម៉ឺន"), (1000, "ពាន់"), (100, "រយ")]
    result = []
    remainder = num
    for val, unit_name in units:
        if remainder >= val:
            count = remainder // val
            remainder %= val
            result.append(f"{khmer_number_to_words(count)} {unit_name}")
    if remainder > 0: result.append(khmer_number_to_words(remainder))
    return " ".join(result)

def format_amount_for_speech(raw_amount: str) -> str:
    cleaned = raw_amount.strip()
    if "$" in cleaned or "." in cleaned:
        clean_num = cleaned.replace("$", "").replace(",", "").strip()
        dollars = 0
        cents = 0
        if "." in clean_num:
            parts = clean_num.split(".", 1)
            d_str = parts[0].strip()
            c_str = parts[1].strip()
            dollars = int(d_str) if d_str.isdigit() else 0
            c_str = (c_str + "0") if len(c_str) == 1 else c_str[:2]
            cents = int(c_str) if c_str.isdigit() else 0
        else:
            dollars = int(clean_num) if clean_num.isdigit() else 0
        speech_parts = []
        if dollars > 0: speech_parts.append(f"{khmer_number_to_words(dollars)} ដុល្លារ")
        if cents > 0: speech_parts.append(f"{khmer_number_to_words(cents)} សេន")
        return " ".join(speech_parts) if speech_parts else "សូន្យ ដុល្លារ"
    
    num_str = cleaned.replace("៛", "").replace(",", "").strip()
    if "." in num_str: num_str = num_str.split(".")[0]
    try:
        r_val = int(num_str)
        return f"{khmer_number_to_words(r_val)} រៀល"
    except ValueError:
        return f"{num_str} រៀល"

async def generate_audio(text):
    global has_new_audio
    # កំណត់ឲ្យបង្កើតសំឡេងទំហំតូចស្តើង (Low Rate/Pitch) កុំឲ្យធ្ងន់ RAM លើ ESP32
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%", pitch="+0Hz")
    await communicate.save(LATEST_AUDIO_FILE)
    has_new_audio = True

# ប្រព័ន្ធរត់ Telegram Client ក្នុង Background
client = TelegramClient("khmer_tts_session", API_ID, API_HASH)

@client.on(events.NewMessage)
async def handler(event):
    text = event.raw_text
    if not text or not text.strip(): return
    chat = await event.get_chat()
    chat_name = getattr(chat, "title", None) or getattr(chat, "username", None) or ""
    if ONLY_FROM_CHATS and not any(name.lower() in chat_name.lower() for name in ONLY_FROM_CHATS): return
    if not any(k.lower() in text.lower() for k in RECEIVE_KEYWORDS): return
    amounts = AMOUNT_PATTERN.findall(text)
    if not amounts: return
    amount_text = " និង ".join(format_amount_for_speech(a) for a in amounts)
    
    # បង្កើតសំឡេង AI
    await generate_audio(f"ទទួលបាន {amount_text}")

# ផ្លូវទាញយកសំឡេងសម្រាប់ ESP32 Sound Box
@app.route('/latest-audio')
def get_latest_audio():
    global has_new_audio
    if os.path.exists(LATEST_AUDIO_FILE):
        return send_from_directory('.', LATEST_AUDIO_FILE)
    return jsonify({"status": "no audio"}), 404

# បង្កើតប្រព័ន្ធពិនិត្យមើលស្ថានភាពសំឡេងថ្មី
@app.route('/check-status')
def check_status():
    global has_new_audio
    if has_new_audio:
        has_new_audio = False # Reset បន្ទាប់ពី ESP32 ដឹង
        return jsonify({"has_new": True})
    return jsonify({"has_new": False})

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
