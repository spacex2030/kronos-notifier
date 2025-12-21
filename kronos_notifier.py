#!/usr/bin/env python3
"""
Kronos Gold Price Notifier
Monitors gold prices from your website and sends notifications via Telegram
when conditions are met
"""

import os
import re
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
    try:
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print(f"✓ Message sent to {chat_id}")
            return True
        else:
            print(f"✗ Error: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error sending message: {e}")
        return False


def fa_to_en_digits(s: str) -> str:
    """Convert Persian digits to English digits"""
    fa = "۰۱۲۳۴۵۶۷۸۹"
    en = "0123456789"
    table = str.maketrans(fa, en)
    return s.translate(table)


def extract_number(text: str):
    """Extract float value from a mixed string (supports Persian/English digits)"""
    if text is None:
        return None
    # حذف جداکننده‌های هزارگان و فاصله‌ها
    cleaned = text.replace("٬", "").replace(",", "").strip()
    cleaned = fa_to_en_digits(cleaned)
    m = re.search(r"(-?\d+(\.\d+)?)", cleaned)
    return float(m.group(1)) if m else None


def get_text(elem) -> str | None:
    if elem is None:
        return None
    if isinstance(elem, str):
        return elem
    return elem.get_text()


def get_value_after_label(elem, label: str):
    """Extract numeric value that comes after a label like 'Base:' or 'SL:'"""
    text = get_text(elem)
    if not text:
        return None
    if label in text:
        after = text.split(label, 1)[1]
    else:
        after = text
    return extract_number(after)


def check_kronos_price():
    """Fetch and parse data from your Kronos website"""
    try:
        url = "http://93.118.110.114:8080/"
        print(f"Fetching data from {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        # برای دیباگ در صورت نیاز:
        # print(response.text[:4000])

        soup = BeautifulSoup(response.text, "html.parser")

        # عناصر متنی بر اساس برچسب‌ها (بدون وابستگی به $ و الگوی سخت)
        base_elem = soup.find(string=re.compile(r"Base:"))
        target_elem = soup.find(string=re.compile(r"Target:"))
        sl_elem = soup.find(string=re.compile(r"SL:"))
        delta_elem = soup.find(string=re.compile(r"Δ"))
        state_elem = soup.find(string=re.compile(r"State:"))
        kronos_elem = soup.find(string=re.compile(r"Kronos:"))

        # مقادیر عددی
        base_price = get_value_after_label(base_elem, "Base:")
        target_price = get_value_after_label(target_elem, "Target:")
        sl_price = get_value_after_label(sl_elem, "SL:")

        # Kronos (اول تلاش برای مقدار جداگانه بعد از Kronos،
        # اگر نبود، از Target استفاده می‌شود)
        kronos_price = None
        if kronos_elem:
            parent = kronos_elem.parent
            if parent:
                # معمولاً قیمت بعد از Kronos در نود بعدی می‌آید
                next_text_elem = parent.find_next(string=True)
                kronos_price = extract_number(get_text(next_text_elem))
        if kronos_price is None:
            kronos_price = target_price

        # Delta درصدی
        delta = None
        if delta_elem:
            delta_text = get_text(delta_elem)
            if delta_text:
                # مثال: "Δ 1.23%" یا "Δ: ۱٫۲۳٪"
                delta_match = re.search(
                    r"(-?\d+(\.\d+)?)", fa_to_en_digits(delta_text)
                )
                if delta_match:
                    delta = float(delta_match.group(1))

        # State
        state = None
        if state_elem:
            state_text = get_text(state_elem)
            if state_text:
                if "State:" in state_text:
                    state = state_text.split("State:", 1)[1].strip()
                else:
                    state = state_text.strip()

        if base_price is None or kronos_price is None:
            print("⚠ Could not parse prices from website")
            return None

        # Calculate difference
        difference = kronos_price - base_price
        print(f"Base Price: ${base_price:.2f}")
        print(f"Kronos Prediction: ${kronos_price:.2f}")
        print(f"Difference: ${difference:.2f}")

        # Check if difference is greater than $3.5
        should_notify = abs(difference) > 3.5

        return {
            "base_price": base_price,
            "kronos_price": kronos_price,
            "target_price": target_price,
            "sl_price": sl_price,
            "difference": difference,
            "delta": delta,
            "state": state,
            "should_notify": should_notify,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"Error checking Kronos price: {e}")
        import traceback

        traceback.print_exc()
        return None


def main():
    """Main function"""
    print("\n=== Kronos Gold Price Notifier ===")
    print(f"Started at: {datetime.now().isoformat()}")

    try:
        # Get Telegram credentials
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if not bot_token or not chat_id:
            print(
                "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables"
            )
            return

        # Check Kronos price
        result = check_kronos_price()
        if result is None:
            print("Failed to check Kronos price")
            return

        print(f"Should Notify: {result['should_notify']}")

        # If conditions are met, send notification
        if result["should_notify"]:
            # Format message with all information
            message = f"""🔔 <b>Kronos Gold Price Alert</b>

📊 <b>Price Information:</b>
• Base Price: ${result['base_price']:.2f}
• Kronos Prediction: ${result['kronos_price']:.2f}
• Difference: ${result['difference']:.2f}"""

            if result["target_price"]:
                message += f"\n• Target: ${result['target_price']:.2f}"
            if result["sl_price"]:
                message += f"\n• Stop Loss: ${result['sl_price']:.2f}"
            if result["delta"] is not None:
                message += f"\n• Delta: {result['delta']}%"
            if result["state"]:
                message += f"\n• State: {result['state']}"

            message += (
                f"\n\n⏰ <b>Time:</b> {result['timestamp']}"
                f"\n💡 <i>Difference exceeds $3.5 threshold</i>"
            )

            send_telegram_message(bot_token, chat_id, message)
        else:
            print(
                f"✓ Price difference (${abs(result['difference']):.2f}) "
                "is below $3.5 threshold"
            )

        print("✓ Check completed successfully")

    except Exception as e:
        print(f"Error in main: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
