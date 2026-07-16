import os
from flask import Flask, request, send_from_directory, jsonify
import edge_tts
import asyncio
import re

app = Flask(__name__)

VOICE = "km-KH-PisethNeural"
LATEST_AUDIO_FILE = "latest_audio.mp3"

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

async def generate_audio_async(text):
    if os.path.exists(LATEST_AUDIO_FILE):
        try:
            os.remove(LATEST_AUDIO_FILE)
        except:
            pass
    communicate = edge_tts.Communicate(text, VOICE, rate="+10%", pitch="+0Hz")
    await communicate.save(LATEST_AUDIO_FILE)

@app.route('/')
def home():
    return "Server Soundbox is Online!"

# 💡 API សម្រាប់ទទួលសារពី Telegram Bot
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 ទទួលបានទិន្នន័យ:", data)
    
    message_text = ""
    if data and 'message' in data and 'text' in data['message']:
        message_text = data['message']['text']
    elif data and 'channel_post' in data and 'text' in data['channel_post']:
        message_text = data['channel_post']['text']
        
    if message_text:
        AMOUNT_PATTERN = re.compile(r'(\d[\d,]*\.?\d*)')
        amounts = AMOUNT_PATTERN.findall(message_text)
        if amounts:
            amount_text = " និង ".join([format_amount_for_speech(a) for a in amounts])
            speech_text = f"ទទួលបាន {amount_text}"
            
            # បង្កើត File សំឡេង
            asyncio.run(generate_audio_async(speech_text))
            print(f"✅ បង្កើតសំឡេងរួចរាល់: {speech_text}")
            
    return jsonify({"status": "success"}), 200

@app.route('/latest-audio')
def get_latest_audio():
    if os.path.exists(LATEST_AUDIO_FILE):
        return send_from_directory('.', LATEST_AUDIO_FILE)
    return jsonify({"status": "no audio"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
