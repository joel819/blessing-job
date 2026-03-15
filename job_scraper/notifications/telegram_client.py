import os
import requests

# Recommendation: Store these in environment variables or a config file
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8536955372:AAGMyomvxsNK3s2EEm1oWOfFiwaFHjAC1S0")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "686525754")

def send_telegram(text):
    """
    Send a message to a Telegram chat via the Bot API.
    
    Args:
        text (str): The message content to send.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("Telegram message sent successfully.")
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
