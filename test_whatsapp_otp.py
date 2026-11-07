"""
Test your Free WhatsApp OTP integration (Option 1).
Run with: python test_whatsapp_otp.py
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv(Path(__file__).resolve().parent / ".env")

from app.sms import send_real_otp

def test_whatsapp():
    print("\n" + "=" * 55)
    print("📲 Testing Free WhatsApp OTP Delivery (CallMeBot)")
    print("=" * 55)

    api_key = os.getenv("CALLMEBOT_API_KEY", "").strip()
    if not api_key:
        print("❌ CALLMEBOT_API_KEY is not set in your .env file yet!")
        print("\n👉 How to get your free API key in 30 seconds:")
        print("1. Open WhatsApp and message: 'I allow callmebot to send me messages'")
        print("   to: +34 911 06 14 53")
        print("2. CallMeBot will reply with your API Key.")
        print("3. Add it to .env: CALLMEBOT_API_KEY=\"your_key\"")
        print("=" * 55 + "\n")
        sys.exit(1)

    phone = input("Enter your 10-digit WhatsApp phone number to test (e.g. 9876543210): ").strip()
    if not phone:
        print("No phone number entered. Exiting.")
        sys.exit(1)

    test_otp = "482910"
    print(f"\n🚀 Sending test OTP ({test_otp}) to WhatsApp: {phone}...")
    res = send_real_otp(phone, test_otp)

    if res.get("success"):
        print("\n✅ SUCCESS! Check your WhatsApp chat — your real OTP just arrived!")
    else:
        print("\n⚠️ Delivery notice:", res)

    print("=" * 55 + "\n")

if __name__ == "__main__":
    test_whatsapp()

