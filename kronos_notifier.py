#!/usr/bin/env python3
"""
Kronos Gold Price Notifier
Monitors gold prices and sends notifications via Telegram when conditions are met
"""

import os
import requests
from datetime import datetime

def send_telegram_message(bot_token, chat_id, message):
    """Send message to Telegram using HTTP API"""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message
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

def check_gold_price():
    """Check gold price and determine if conditions are met"""
    try:
        # Placeholder for actual API call to get gold price
        # You can replace this with your actual Kronos API or any gold price API
        print("Checking gold price...")
        
        # Example: You could use an API like:
        # response = requests.get('https://api.example.com/gold-price')
        # price = response.json()['price']
        
        # For now, this is a placeholder
        return {
            'price': 2650000,
            'should_notify': True,
            'message': 'Gold price check completed',
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error checking gold price: {e}")
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
        
        # Check gold price
        result = check_gold_price()
        
        if result is None:
            print("Failed to check gold price")
            return
        
        print(f"Price: {result['price']}")
        print(f"Should Notify: {result['should_notify']}")
        
        # If conditions are met, send notification
        if result['should_notify']:
            message = f"🔔 Gold Price Alert\n\n{result['message']}\nPrice: {result['price']}\nTime: {result['timestamp']}"
            send_telegram_message(bot_token, chat_id, message)
        
        print("✓ Check completed successfully")
    except Exception as e:
        print(f"Error in main: {e}")

if __name__ == "__main__":
    main()
