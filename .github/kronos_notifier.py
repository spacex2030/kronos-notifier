import socketio
import time
import requests
from datetime import datetime
import os

# تلگرام
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
PREDICTION_SERVER_URL = "http://93.118.110.114:8080"

def send_telegram_message(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram token/chat_id not set")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print("✅ پیام به تلگرام فرستاده شد")
        else:
            print(f"❌ خطا: {r.status_code}")
    except Exception as e:
        print(f"❌ خطا در ارسال: {e}")

def should_trade(base_price, kronos_price) -> bool:
    return abs(kronos_price - base_price) > 3.5

def get_gold_predictions():
    sio = socketio.Client()
    prediction_data = {}

    @sio.event
    def connect():
        print("🔗 وصل شدن به سرور...")
        sio.emit("request_initial_data")

    @sio.on("update_all")
    def on_update_all(data):
        nonlocal prediction_data
        if "results" not in data or not data["results"]:
            return

        results = data["results"]
        base_price = None
        kronos_pred = None
        server_time = None

        for tf in ["H1", "1H", "h1", "M15", "m15"]:
            if tf in results and "base_price" in results[tf]:
                try:
                    base_str = str(results[tf]["base_price"]).replace(",", "").replace(" ", "")
                    base_price = float(base_str)
                    if "kronos_pred" in results[tf] and results[tf]["kronos_pred"]:
                        kronos_pred = float(results[tf]["kronos_pred"])
                    if "timestamp" in results[tf]:
                        server_time = results[tf]["timestamp"]
                    break
                except Exception:
                    continue

        if kronos_pred is None and "kronos_data" in data and "predicted_price" in data["kronos_data"]:
            try:
                kronos_pred = float(data["kronos_data"]["predicted_price"])
            except:
                pass

        if server_time is None and "news" in data and "last_update" in data["news"]:
            server_time = data["news"]["last_update"]

        if base_price is not None and kronos_pred is not None:
            prediction_data = {
                "base_price": base_price,
                "kronos_price": kronos_pred,
                "server_time": server_time,
            }
            if "kronos_data" in data:
                kd = data["kronos_data"]
                prediction_data["decision"] = kd.get("decision")
                prediction_data["confidence"] = kd.get("confidence")
            sio.disconnect()

    try:
        print(f"📡 اتصال به {PREDICTION_SERVER_URL}...")
        sio.connect(PREDICTION_SERVER_URL)
        timeout = 10
        start_time = time.time()
        while (time.time() - start_time) < timeout and not prediction_data:
            time.sleep(0.1)
        sio.disconnect()
    except Exception as e:
        print(f"❌ خطا در اتصال: {e}")
        return None

    return prediction_data if prediction_data else None

def main():
    print("=" * 50)
    print("🤖 Kronos Notifier شروع شد")
    print("=" * 50)
    
    data = get_gold_predictions()
    if not data:
        print("❌ اطلاعات دریافت نشد")
        return

    base_price = data["base_price"]
    kronos_price = data["kronos_price"]
    server_time = data.get("server_time")
    decision = data.get("decision", "Unknown")
    confidence = data.get("confidence") or 0.0

    print(f"\n📊 داده‌های دریافت شده:")
    print(f"  قیمت پایه: {base_price:,.2f} $")
    print(f"  قیمت کرونوس: {kronos_price:,.2f} $")
    print(f"  اختلاف: {abs(kronos_price - base_price):.2f} $")

    if not should_trade(base_price, kronos_price):
        print(f"\n⏸️  شرط سیگنال برقرار نیست (حد: 3.5 $)")
        return

    print(f"\n✨ شرط برقرار شد! ارسال به تلگرام...")

    now = datetime.utcnow()
    lines = [
        "📡 <b>سیگنال Kronos</b> (GitHub Actions)",
        "",
        f"📅 تاریخ: {now.strftime('%Y-%m-%d')}",
        f"⏰ زمان: {now.strftime('%H:%M:%S')} UTC",
        "",
        f"💰 قیمت پایه: <code>{base_price:,.2f} $</code>",
        f"🎯 قیمت کرونوس: <code>{kronos_price:,.2f} $</code>",
        f"📈 اختلاف: <code>{abs(kronos_price - base_price):.2f} $</code>",
    ]
    
    if server_time:
        lines.append(f"🕐 زمان سرور: {server_time}")
    
    if decision != "Unknown":
        lines.append(f"🔮 تصمیم: {decision}")
    
    lines.append(f"📊 اطمینان: {float(confidence):.3f}")

    text = "\n".join(lines)
    send_telegram_message(text)
    print("✅ کار تمام شد!")

if __name__ == "__main__":
    main()
