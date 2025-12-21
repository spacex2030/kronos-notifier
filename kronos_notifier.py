#!/usr/bin/env python3
"""
Kronos Gold Price Notifier
Monitors gold prices from your website and sends notifications via Telegram when conditions are met
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
        "parse_mode": "HTML"
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

def parse_price(price_str):
    """Parse price string and convert to float"""
    # Remove Persian/Arabic numerals and convert to English
    persian_to_english = str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')
    price_str = price_str.translate(persian_to_english)
    # Remove commas and dollar sign
    price_str = price_str.replace(',', '').replace('٬', '').replace('$', '').strip()
    try:
        return float(price_str)
    except:
        return None

def check_kronos_price():
    """Fetch and parse data from your Kronos website"""
    try:
        url = 'http://93.118.110.114:8080/'
        print(f"Fetching data from {url}...")
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find Base price
        base_elem = soup.find(text=re.compile(r'Base:.*\$'))
        base_price = None
        if base_elem:
            match = re.search(r'Base:\s*([\d٬,\.۰-۹]+)\s*\$', base_elem)
            if match:
                base_price = parse_price(match.group(1))
        
        # Find Target (Kronos) price
        target_elem = soup.find(text=re.compile(r'Target:.*\$'))
        target_price = None
        if target_elem:
            match = re.search(r'Target:\s*([\d٬,\.۰-۹]+)\s*\$', target_elem)
            if match:
                target_price = parse_price(match.group(1))
        
        # Find the green consensus value (actual Kronos prediction)
        kronos_elem = soup.find(text=re.compile(r'Kronos:'))
        kronos_price = None
        if kronos_elem:
            # Try to find the price after "Kronos:"
            parent = kronos_elem.parent
            if parent:
                # Look for the next element or text
                next_elem = parent.find_next()
                if next_elem:
                    price_text = next_elem.get_text()
                    kronos_price = parse_price(price_text)
        
        # If we couldn't find Kronos price separately, use Target as Kronos
        if kronos_price is None:
            kronos_price = target_price
        
        # Find State
        state_elem = soup.find(text=re.compile(r'State:'))
        state = None
        if state_elem:
            match = re.search(r'State:\s*(.+)', state_elem)
            if match:
                state = match.group(1).strip()
        
        # Find SL (Stop Loss)
        sl_elem = soup.find(text=re.compile(r'SL:.*\$'))
        sl_price = None
        if sl_elem:
            match = re.search(r'SL:\s*([\d٬,\.۰-۹]+)\s*\$', sl_elem)
            if match:
                sl_price = parse_price(match.group(1))
        
        # Find Delta percentage
        delta_elem = soup.find(text=re.compile(r'Δ\s*[\d\.]+%'))
        delta = None
        if delta_elem:
            match = re.search(r'Δ\s*([\d\.]+)%', delta_elem)
            if match:
                delta = match.group(1)
        
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
            'base_price': base_price,
            'kronos_price': kronos_price,
            'target_price': target_price,
            'sl_price': sl_price,
            'difference': difference,
            'delta': delta,
            'state': state,
            'should_notify': should_notify,
            'timestamp': datetime.now().isoformat()
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
        bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
        chat_id = os.environ.get('TELEGRAM_CHAT_ID')
        
        if not bot_token or not chat_id:
            print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID environment variables")
            return
        
        # Check Kronos price
        result = check_kronos_price()
        
        if result is None:
            print("Failed to check Kronos price")
            return
        
        print(f"Should Notify: {result['should_notify']}")
        
        # If conditions are met, send notification
        if result['should_notify']:
            # Format message with all information
            message = f"""🔔 <b>Kronos Gold Price Alert</b>

📊 <b>Price Information:</b>
• Base Price: ${result['base_price']:.2f}
• Kronos Prediction: ${result['kronos_price']:.2f}
• Difference: ${result['difference']:.2f}

📈 <b>Additional Data:</b>"""
            
            if result['target_price']:
                message += f"\n• Target: ${result['target_price']:.2f}"
            if result['sl_price']:
                message += f"\n• Stop Loss: ${result['sl_price']:.2f}"
            if result['delta']:
                message += f"\n• Delta: {result['delta']}%"
            if result['state']:
                message += f"\n• State: {result['state']}"
            
            message += f"""\n\n⏰ <b>Time:</b> {result['timestamp']}

💡 <i>Difference exceeds $3.5 threshold</i>"""
            
            send_telegram_message(bot_token, chat_id, message)
        else:
            print(f"✓ Price difference (${abs(result['difference']):.2f}) is below $3.5 threshold")
        
        print("✓ Check completed successfully")
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
