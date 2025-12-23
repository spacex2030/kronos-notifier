#!/usr/bin/env python3
"""
Kronos Gold Price Notifier
Stable version – no Telegram HTML parsing errors
"""

import os
import re
import json
import time
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo  # Python 3.9+
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


def send_telegram_message(bot_token, chat_id, message):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    # Remove @ if present and ensure chat_id is treated as string
    chat_id_clean = str(chat_id).lstrip('@')
    data = {
        "chat_id": chat_id_clean,
        "text": message,   # ❌ no parse_mode
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code == 200:
            print("✓ Message sent to Telegram")
            return True
        else:
            error_data = response.json() if response.text else {}
            error_desc = error_data.get("description", response.text)
            print(f"✗ Telegram error: {error_desc}")
            if "chat not found" in error_desc.lower():
                print("  → Tip: How to get your chat_id:")
                print("    1. For personal chat: Start a conversation with @userinfobot")
                print("       It will show your numeric ID (e.g., 123456789)")
                print("    2. For channels: Use @channel_username format")
                print("    3. For groups: Add @RawDataBot to your group, it will show the group ID")
                print("    4. Make sure you've sent at least one message to the bot first")
                print(f"    5. Current chat_id being used: {chat_id_clean}")
                print("\n  → Trying to find available chat IDs...")
                get_telegram_chat_id(bot_token)
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"✗ Network error: Could not connect to Telegram API")
        print(f"  → Check your internet connection or firewall settings")
        print(f"  → Error details: {str(e)[:100]}")
        return False
    except requests.exceptions.Timeout:
        print(f"✗ Timeout error: Telegram API did not respond in time")
        return False
    except Exception as e:
        print(f"✗ Unexpected error sending Telegram message: {e}")
        return False


def get_telegram_chat_id(bot_token):
    """
    Helper function to get recent chat IDs from bot updates.
    This can help identify the correct chat_id.
    """
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") and data.get("result"):
                updates = data["result"]
                if updates:
                    print("\n📋 Recent chat IDs found:")
                    seen_chats = set()
                    for update in updates[-5:]:  # Show last 5 updates
                        chat = update.get("message", {}).get("chat", {})
                        chat_id = chat.get("id")
                        chat_type = chat.get("type")
                        chat_title = chat.get("title") or chat.get("first_name", "Unknown")
                        if chat_id and chat_id not in seen_chats:
                            seen_chats.add(chat_id)
                            print(f"  - Chat ID: {chat_id} (Type: {chat_type}, Name: {chat_title})")
                    if seen_chats:
                        print(f"\n💡 Try using one of these chat IDs as TELEGRAM_CHAT_ID")
                    else:
                        print("  No recent messages found. Send a message to your bot first.")
                else:
                    print("  No updates found. Send a message to your bot first.")
            else:
                print(f"  Error: {data.get('description', 'Unknown error')}")
        else:
            print(f"  Failed to get updates: HTTP {response.status_code}")
    except Exception as e:
        print(f"  Error getting chat IDs: {e}")


def fa_to_en_digits(s: str) -> str:
    fa = "۰۱۲۳۴۵۶۷۸۹"
    en = "0123456789"
    return s.translate(str.maketrans(fa, en))


def extract_number(text: str):
    if not text:
        return None
    text = fa_to_en_digits(text)
    text = text.replace(",", "").replace("٬", "")
    m = re.search(r"(-?\d+(\.\d+)?)", text)
    return float(m.group(1)) if m else None


def get_text(elem):
    if elem is None:
        return None
    return elem if isinstance(elem, str) else elem.get_text()


def get_value_after_label(elem, label):
    if elem is None:
        return None
    # If it's a NavigableString, get parent element's text
    if hasattr(elem, 'parent') and elem.parent:
        text = elem.parent.get_text()
    else:
        text = get_text(elem)
    if not text:
        return None
    after = text.split(label, 1)[1] if label in text else text
    return extract_number(after)


def decode_engineio_payload(payload: str):
    packets = []
    i = 0
    while i < len(payload):
        if payload[i].isdigit():
            j = i
            while j < len(payload) and payload[j].isdigit():
                j += 1
            if j < len(payload) and payload[j] == ":":
                length = int(payload[i:j])
                j += 1
                packets.append(payload[j:j + length])
                i = j + length
                continue
        packets.append(payload[i:])
        break
    return packets


def fetch_update_all_via_socketio(base_url: str, timeout: int = 15, max_polls: int = 5):
    try:
        session = requests.Session()
        params = {"EIO": "4", "transport": "polling", "t": str(int(time.time() * 1000))}
        resp = session.get(f"{base_url}/socket.io/", params=params, timeout=timeout)
        resp.raise_for_status()
        sid = None
        for packet in decode_engineio_payload(resp.text):
            if packet.startswith("0"):
                try:
                    data = json.loads(packet[1:])
                except Exception:
                    data = {}
                sid = data.get("sid")
                break
        if not sid:
            return None

        session.post(
            f"{base_url}/socket.io/",
            params={"EIO": "4", "transport": "polling", "sid": sid},
            data="40",
            timeout=timeout,
        )

        for _ in range(max_polls):
            poll = session.get(
                f"{base_url}/socket.io/",
                params={"EIO": "4", "transport": "polling", "sid": sid, "t": str(int(time.time() * 1000))},
                timeout=timeout,
            )
            poll.raise_for_status()
            for packet in decode_engineio_payload(poll.text):
                if not packet.startswith("42"):
                    continue
                try:
                    event, data = json.loads(packet[2:])
                except Exception:
                    continue
                if event == "update_all":
                    return data
            time.sleep(0.2)
    except Exception:
        return None
    return None


def compute_tp_sl(base, pred):
    if not base or not pred:
        return pred or base, base
    diff = abs(pred - base)
    sl = base - 0.5 * diff if pred > base else base + 0.5 * diff
    return pred, sl


def select_timeframe(results, preferred):
    if preferred and preferred in results:
        return preferred
    for tf in ["H1", "M30", "M15", "M5", "M1", "H4", "D1", "W1", "MN"]:
        if tf in results:
            return tf
    return sorted(results.keys())[0] if results else None


def parse_socketio_payload(data, preferred_tf=None):
    results = data.get("results") or {}
    if not results:
        return None
    tf = select_timeframe(results, preferred_tf)
    if not tf:
        return None
    res = results.get(tf) or {}
    base_price = res.get("base_price")
    pred_price = res.get("prediction") or res.get("kronos_pred") or base_price
    kronos_price = res.get("kronos_pred") or res.get("prediction") or base_price
    target_price, sl_price = compute_tp_sl(base_price, pred_price)
    cond = (data.get("market_conditions") or {}).get(tf, {})
    state = cond.get("condition_fa") or cond.get("condition")
    return {
        "base_price": base_price,
        "kronos_price": kronos_price,
        "target_price": target_price,
        "sl_price": sl_price,
        "state": state,
        "timeframe": tf,
    }


def check_kronos_price():
    try:
        url = os.environ.get("KRONOS_URL", "http://93.118.110.114:8080/")
        print(f"Fetching data from {url}...")

        base_url = url.rstrip("/")
        socket_data = fetch_update_all_via_socketio(base_url)
        if socket_data:
            preferred_tf = os.environ.get("KRONOS_TIMEFRAME")
            parsed = parse_socketio_payload(socket_data, preferred_tf)
            if parsed and parsed.get("base_price") and parsed.get("kronos_price"):
                difference = parsed["kronos_price"] - parsed["base_price"]
                print(f"Using Socket.IO data (timeframe: {parsed.get('timeframe')})")
                print(f"Base Price: ${parsed['base_price']:.2f}")
                print(f"Kronos Prediction: ${parsed['kronos_price']:.2f}")
                print(f"Difference: ${difference:.2f}")
                return {
                    "base_price": parsed["base_price"],
                    "kronos_price": parsed["kronos_price"],
                    "target_price": parsed.get("target_price"),
                    "sl_price": parsed.get("sl_price"),
                    "state": parsed.get("state"),
                    "difference": difference,
                    "should_notify": abs(difference) > 3.5,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            print("Socket.IO data incomplete, falling back to HTML parsing...")
        
        # Try using Selenium if available to get dynamic content
        if SELENIUM_AVAILABLE:
            try:
                print("Using Selenium to load dynamic content...")
                chrome_options = Options()
                chrome_options.add_argument("--headless")
                chrome_options.add_argument("--no-sandbox")
                chrome_options.add_argument("--disable-dev-shm-usage")
                chrome_options.add_argument("--disable-gpu")
                chrome_options.add_argument("--window-size=1920,1080")
                
                driver = webdriver.Chrome(options=chrome_options)
                driver.get(url)
                
                # Wait for content to load (wait for elements with "Base:" text)
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: "Base:" in d.page_source and "$" in d.page_source
                    )
                    print("Page loaded, extracting data...")
                    html = driver.page_source
                    driver.quit()
                except Exception as e:
                    print(f"Selenium wait timeout: {e}")
                    html = driver.page_source
                    driver.quit()
                
                soup = BeautifulSoup(html, "html.parser")
            except Exception as e:
                print(f"Selenium failed: {e}, falling back to requests...")
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
        else:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        
        # Try to extract JSON data from script tags first (common pattern)
        json_data = None
        for script in soup.find_all("script"):
            if script.string:
                # Look for JSON-like data structures
                script_text = script.string
                # Try to find JSON objects with base_price or similar
                if "base_price" in script_text or "Base:" in script_text:
                    try:
                        # Try to extract JSON from script
                        import json as json_module
                        # Look for JSON objects
                        json_match = re.search(r'\{[^{}]*"base_price"[^{}]*\}', script_text)
                        if json_match:
                            json_data = json_module.loads(json_match.group())
                            print("DEBUG: Found JSON data in script")
                    except:
                        pass
        
        # Remove script and style tags to avoid matching JavaScript code
        for script in soup(["script", "style"]):
            script.decompose()

        # Try to find elements containing the labels (excluding script tags)
        def find_label_value(label):
            # Search in all text nodes, but exclude script/style content
            for elem in soup.find_all(string=re.compile(f"{label}")):
                # Make sure it's not inside a script tag
                parent = elem.parent if hasattr(elem, 'parent') else None
                if parent and parent.name in ['script', 'style']:
                    continue
                value = get_value_after_label(elem, label)
                if value is not None and value > 0:  # Valid price should be > 0
                    return value
            # Last resort: search in cleaned text
            all_text = soup.get_text()
            if label in all_text:
                # Find all occurrences and try each
                import re as re_module
                pattern = re_module.compile(f"{re_module.escape(label)}\\s*([0-9,٬.]+)")
                matches = pattern.findall(all_text)
                for match in matches:
                    val = extract_number(match)
                    if val is not None and val > 0:
                        return val
            return None

        # Find elements (excluding script tags)
        def find_text_node(label):
            for elem in soup.find_all(string=re.compile(f"{label}")):
                parent = elem.parent if hasattr(elem, 'parent') else None
                if parent and parent.name in ['script', 'style']:
                    continue
                return elem
            return None

        base_elem = find_text_node("Base:")
        target_elem = find_text_node("Target:")
        sl_elem = find_text_node("SL:")
        kronos_elem = find_text_node("Kronos:")
        state_elem = find_text_node("State:")

        # Debug: print what we found
        if base_elem:
            base_text = get_text(base_elem)
            if len(base_text) < 200:  # Only show if reasonable length
                print(f"DEBUG: Found Base element: {repr(base_text[:100])}")
        else:
            print("DEBUG: Base element not found in HTML, trying text search...")
            if not SELENIUM_AVAILABLE:
                print("  → Tip: Install selenium for better dynamic content support:")
                print("     pip install selenium")
                print("     (Also requires Chrome browser and chromedriver)")

        base_price = get_value_after_label(base_elem, "Base:")
        if base_price is None or base_price == 0:
            base_price = find_label_value("Base:")
        target_price = get_value_after_label(target_elem, "Target:")
        if target_price is None:
            target_price = find_label_value("Target:")
        sl_price = get_value_after_label(sl_elem, "SL:")
        if sl_price is None:
            sl_price = find_label_value("SL:")

        # Try to find prices in HTML elements with specific classes/attributes
        # Look for elements with class containing "badge" or "price" or similar
        def find_price_in_elements():
            # Try finding elements by class names that might contain prices
            price_elements = soup.find_all(class_=re.compile("badge|price|tf-badge|tf-meta", re.I))
            for elem in price_elements:
                text = elem.get_text()
                if "Base:" in text:
                    val = get_value_after_label(text, "Base:")
                    if val and val > 0:
                        return val
            # Also try finding by text content in divs/spans
            for elem in soup.find_all(['div', 'span', 'td', 'th']):
                text = elem.get_text()
                if "Base:" in text and "$" in text:
                    # Extract the number after Base: and before $
                    match = re.search(r'Base:\s*([0-9,٬.]+)', text)
                    if match:
                        val = extract_number(match.group(1))
                        if val and val > 0:
                            return val
            return None
        
        # Try finding in HTML elements first
        if base_price is None or base_price == 0:
            base_price = find_price_in_elements()
        
        # If still not found, try searching the entire page text more carefully
        if base_price is None or base_price == 0:
            page_text = soup.get_text()
            # Look for patterns like "Base: 2,500.00 $" or "Base:2500"
            base_patterns = [
                r'Base:\s*([0-9,٬.]+)\s*\$',
                r'Base[:\s]+([0-9,٬.]+)',
            ]
            for pattern in base_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for match in matches:
                    val = extract_number(match)
                    if val and val > 1000:  # Gold price should be > 1000
                        base_price = val
                        print(f"DEBUG: Found Base price via pattern: {val}")
                        break
                if base_price and base_price > 1000:
                    break
        
        kronos_price = None
        if kronos_elem:
            kronos_price = extract_number(get_text(kronos_elem))
        if kronos_price is None:
            # Try to find Kronos price in HTML elements
            kronos_elems = soup.find_all(string=re.compile("Kronos:"))
            for ke in kronos_elems:
                parent = ke.parent if hasattr(ke, 'parent') else None
                if parent and parent.name in ['script', 'style']:
                    continue
                kp = get_value_after_label(ke, "Kronos:")
                if kp and kp > 0:
                    kronos_price = kp
                    break
        if kronos_price is None:
            kronos_price = target_price

        state = None
        if state_elem:
            txt = get_text(state_elem)
            state = txt.split("State:", 1)[1].strip() if "State:" in txt else txt.strip()

        if base_price is None or kronos_price is None:
            print("⚠ Could not parse prices")
            return None

        difference = kronos_price - base_price

        print(f"Base Price: ${base_price:.2f}")
        print(f"Kronos Prediction: ${kronos_price:.2f}")
        print(f"Difference: ${difference:.2f}")

        return {
            "base_price": base_price,
            "kronos_price": kronos_price,
            "target_price": target_price,
            "sl_price": sl_price,
            "state": state,
            "difference": difference,
            "should_notify": abs(difference) > 3.5,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    except Exception as e:
        print(f"Error checking price: {e}")
        return None

def should_run_now():
    tehran_tz = ZoneInfo("Asia/Tehran")
    now_tehran = datetime.now(tehran_tz)
    minute = now_tehran.minute
    second = now_tehran.second
    return (minute % 15 == 0) and (5 <= second <= 15)
def main():
    # time.sleep(8)  # Disabled: timing check conflict
        if not should_run_now():
            print("Not in scheduled 15-min window (needs minute divisible by 15 and second 5-15 sec).")
            return
    print(f"\n=== Kronos Gold Price Notifier ===")
    print(f"Started at: {datetime.now().isoformat()}")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        return

    result = check_kronos_price()
    if not result:
        return

    print(f"Should Notify: {result['should_notify']}")

    if result["should_notify"]:
        message = (
            "Kronos Gold Price Alert\n\n"
            f"Base Price: ${result['base_price']:.2f}\n"
            f"Kronos Price: ${result['kronos_price']:.2f}\n"
            f"Difference: ${result['difference']:.2f}\n"
        )

        if result["target_price"] is not None:
            message += f"Target: ${result['target_price']:.2f}\n"
        if result["sl_price"] is not None:
            message += f"Stop Loss: ${result['sl_price']:.2f}\n"
        if result["state"]:
            message += f"State: {result['state']}\n"

        message += f"\nTime: {result['timestamp']}"

        send_telegram_message(bot_token, chat_id, message)

    print("✓ Check completed successfully")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Script interrupted by user")
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
