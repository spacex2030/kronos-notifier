#!/usr/bin/env python3
"""
Kronos Gold Price Notifier
Monitors gold prices from your website and sends notifications via Telegram
when conditions are met
"""

import os
import re
import html
import requests
from datetime import datetime
from bs4 import BeautifulSoup


def send_telegram_message(bot_token, chat_id, message):
    """Send message to Telegram using HTTP API"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        print(f"✓ Message sent to {chat_id}")
        return True
    else:
        print(f"✗ Error: {response.text}")
        return False


def fa_to_en_digits(s: str) -> str:
    """Convert Persian digits to English digits"""
    fa = "۰۱۲۳۴۵۶۷۸۹"
    en = "0123456789"
    return s.translate(str.maketrans(fa, en))


def extract_number(text: str):
    """Extract float value from a mixed string"""
    if not text:
        return None
    cleaned = text.replace("٬", "").replace(",", "").strip()
    cleaned = fa_to_en_digits(cleaned)
    m = re.search(r"(-?\d+(\.\d+)?)", cleaned)
    return float(m.group(1)) if m else None


def get_text(elem):
    if elem is None:
        return None
    return elem if isinstance(elem, str) else elem.get_text()


def get_value_after_label(elem, label: str):
    text = get_text(elem)
    if not text:
        return None
    after = text.split(label, 1)[1] if label in text else text
    return extract_number(after)


def check_kronos_price():
    try:
        url = "http://93.118.110.114:8080/"
        print(f"Fetching data from {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        base_elem = soup.find(string=re.compile(r"Base:"))
        target_elem = soup.find(string=re.compile(r"Target:"))
        sl_elem = soup.find(string=re.compile(r"SL:"))
        delta_elem = soup.find(string=re.compile(r"Δ"))
        state_elem = soup.find(string=re.compile(r"State:"))
        kronos_elem = soup.find(string=re.compile(r"Kronos:"))

        base_price = get_value_after_label(base_elem, "Base:")
        target_price = get_value_after_label(target_elem, "Target:")
        sl_price = get_value_after_label(sl_elem, "SL:")

        kronos_price = None
        if kronos_elem:
            next_text = kronos_elem.parent.find_next(string=True)
            kronos_price = extract_number(get_text(next_text))
        if kronos_price is None:
            kronos_price = target_price

        delta = None
        if delta_elem:
            delta = extract_number(get_text(delta_elem))

        state = None
        if state_elem:
            text = get_text(state_elem)
            state = text.split("State:", 1)[1].strip() if "State:" in text else text.strip()

        if base_price is None or kronos_price is None:
            print("⚠ Could not parse prices")
            return None

        difference = kronos_price - base_price

        return {
            "base_price": base_price,
            "kronos_price": kronos_price,
            "target_price": target_price,
            "sl_price": sl_price,
            "difference": difference,
            "delta": delta,
            "state": state,
            "should_notify": abs(difference) > 3.5,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"Error checking Kronos price: {e}")
        return None


def main():
    print("\n=== Kronos Gold Price Notifier ===")
    print(f"Started at: {datetime.now().isoformat()}")

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Missing Telegram credentials")
        return

    result = check_kronos_price()
    if not result:
        return

    print(f"Should Notify: {result['should_notify']}")

    if result["should_notify"]:
        message = (
            "🔔 <b>Kronos Gold Price Alert</b>\n\n"
            "📊 <b>Price Information:</b>\n"
            f"• Base Price: ${result['base_price']:.2f}\n"
            f"• Kronos Prediction: ${result['kronos_price']:.2f}\n"
            f"• Difference: ${result['difference']:.2f}"
        )

        if result["target_price"] is not None:
            message += f"\n• Target: ${result['target_price']:.2f}"
        if result["sl_price"] is not None:
            message += f"\n• Stop Loss: ${result['sl_price']:.2f}"
        if result["delta"] is not None:
            message += f"\n• Delta: {result['delta']}%"
        if result["state"]:
            message += f"\n• State: {html.escape(result['state'])}"

        message += (
            f"\n\n⏰ <b>Time:</b> {html.escape(result['timestamp'])}\n"
            "💡 <i>Difference exceeds $3.5 threshold</i>"
        )

        send_telegram_message(bot_token, chat_id, message)

    print("✓ Check completed successfully")


if __name__ == "__main__":
    main()
