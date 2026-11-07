import os
import re
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Free SMS & WhatsApp Gateways
CALLMEBOT_API_KEY = os.getenv("CALLMEBOT_API_KEY", "")      # Free WhatsApp OTP API key
TEXTBEE_API_KEY = os.getenv("TEXTBEE_API_KEY", "")          # Free Android SMS gateway
TEXTBEE_DEVICE_ID = os.getenv("TEXTBEE_DEVICE_ID", "")      # Android Device ID from Textbee
FAST2SMS_API_KEY = os.getenv("FAST2SMS_API_KEY", "")        # Commercial Fast2SMS
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

def clean_phone_for_sms(phone: str) -> str:
    """Strips all non-digit characters and returns 10 digit number."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) > 10 and digits.startswith("91"):
        return digits[2:]
    return digits

def send_real_otp(phone: str, otp_code: str) -> dict:
    """
    Sends real OTP using available free or commercial gateways:
    1. CallMeBot (100% Free WhatsApp OTP)
    2. Textbee.dev (Free Android SMS Gateway)
    3. Fast2SMS / Twilio
    4. Console fallback
    """
    clean_phone = clean_phone_for_sms(phone)
    full_intl_phone = "+91" + clean_phone if len(clean_phone) == 10 else ("+" + clean_phone if not clean_phone.startswith("+") else clean_phone)
    message_text = f"🔐 Your Sampark verification code is: {otp_code}. Valid for 10 minutes."

    # 1. Try CallMeBot (100% Free WhatsApp OTP Delivery)
    callmebot_key = os.getenv("CALLMEBOT_API_KEY", "").strip()
    if callmebot_key:
        try:
            encoded_text = urllib.parse.quote(message_text)
            url = f"https://api.callmebot.com/whatsapp.php?phone={full_intl_phone}&text={encoded_text}&apikey={callmebot_key}"
            with httpx.Client(timeout=12) as client:
                resp = client.get(url)
                resp_lower = resp.text.lower()
                if resp.status_code == 200 and ("queued" in resp_lower or "sent" in resp_lower or "success" in resp_lower or "ok" in resp_lower):
                    print(f"\n✅ [CallMeBot] Real WhatsApp OTP delivered to {full_intl_phone} successfully!\n")
                    return {"success": True, "provider": "CallMeBot", "details": resp.text}
                else:
                    print(f"⚠️ [CallMeBot Notice] HTTP {resp.status_code}: {resp.text}")
                    # If it says 'Message queued' in some other phrasing, still treat as success
                    if "error" not in resp_lower and "not found" not in resp_lower and resp.status_code == 200:
                        return {"success": True, "provider": "CallMeBot", "details": resp.text}
        except Exception as e:
            print(f"⚠️ [CallMeBot Exception] {e}")

    # 2. Try Textbee.dev (Free Android SIM Gateway)
    textbee_key = os.getenv("TEXTBEE_API_KEY", "").strip()
    textbee_dev = os.getenv("TEXTBEE_DEVICE_ID", "").strip()
    if textbee_key and textbee_dev:
        try:
            url = f"https://api.textbee.dev/api/v1/gateway/devices/{textbee_dev}/send-sms"
            headers = {
                "x-api-key": textbee_key,
                "Content-Type": "application/json"
            }
            payload = {
                "recipients": [full_intl_phone],
                "message": message_text
            }
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    print(f"✅ [Textbee Android Gateway] Free real carrier SMS sent to {clean_phone}!")
                    return {"success": True, "provider": "Textbee", "details": resp.json()}
                else:
                    print(f"⚠️ [Textbee Error] {resp.text}")
        except Exception as e:
            print(f"⚠️ [Textbee Exception] {e}")

    # 3. Try Fast2SMS (Commercial API)
    fast2sms_key = os.getenv("FAST2SMS_API_KEY", "").strip()
    if fast2sms_key:
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            headers = {
                "authorization": fast2sms_key,
                "Content-Type": "application/json"
            }
            payload = {
                "variables_values": otp_code,
                "route": "otp",
                "numbers": clean_phone
            }
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, headers=headers, json=payload)
                data = resp.json()
                if resp.status_code == 200 and data.get("return") is True:
                    print(f"✅ [Fast2SMS] Real OTP sent to {clean_phone} successfully!")
                    return {"success": True, "provider": "Fast2SMS", "details": data}
                else:
                    print(f"⚠️ [Fast2SMS Error] {data}")
        except Exception as e:
            print(f"⚠️ [Fast2SMS Exception] {e}")

    # 4. Console Fallback
    print("\n" + "=" * 55)
    print(f"📱 [TEST MODE] Generated OTP for {clean_phone}: {otp_code}")
    print(f"   (To get real WhatsApp OTP, set CALLMEBOT_API_KEY in .env)")
    print("=" * 55 + "\n")
    return {"success": False, "provider": "Console", "demo": True}
