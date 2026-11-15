import os
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()

def format_e164_phone(phone: str) -> str:
    """Formats 10-digit number into international E.164 format (+91...)."""
    digits = "".join([c for c in phone if c.isdigit()])
    if len(digits) == 10:
        return f"+91{digits}"
    elif len(digits) > 10 and digits.startswith("91"):
        return f"+{digits}"
    elif not phone.startswith("+"):
        return f"+{digits}"
    return phone

def initiate_masked_call(caller_phone: str, owner_phone: str, vehicle_number: str = "") -> dict:
    """
    Initiates an Uber-style number masked phone call via Twilio:
    1. Dials Caller's phone from Twilio Virtual Number.
    2. When Caller answers, plays: "Connecting your masked call to vehicle owner..."
    3. Bridges call to Owner's phone, showing ONLY the Twilio virtual number.
    4. Neither caller nor owner sees the other person's real number!
    """
    account_sid = (os.getenv("TWILIO_ACCOUNT_SID") or TWILIO_ACCOUNT_SID).strip()
    auth_token = (os.getenv("TWILIO_AUTH_TOKEN") or TWILIO_AUTH_TOKEN).strip()
    twilio_number = (os.getenv("TWILIO_PHONE_NUMBER") or TWILIO_PHONE_NUMBER).strip()

    if not account_sid or not auth_token or not twilio_number:
        return {
            "success": False,
            "error": "Twilio credentials not configured in .env. Please set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER."
        }

    caller_e164 = format_e164_phone(caller_phone)
    owner_e164 = format_e164_phone(owner_phone)

    # Dynamic TwiML voice instruction: connects caller to owner with masked callerId
    plate_announcement = f"for vehicle {vehicle_number}" if vehicle_number else ""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="en-IN">Connecting your masked call to the vehicle owner {plate_announcement}. Please hold.</Say>
    <Dial callerId="{twilio_number}" timeout="30">
        <Number>{owner_e164}</Number>
    </Dial>
</Response>"""

    # Twilio trial accounts require a hosted URL (Twimlet / webhook) rather than inline Twiml
    twiml_url = f"https://twimlets.com/echo?Twiml={urllib.parse.quote(twiml)}"

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json"
    data = {
        "To": caller_e164,
        "From": twilio_number,
        "Url": twiml_url
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(
                url,
                data=data,
                auth=(account_sid, auth_token)
            )
            resp_data = resp.json()

            if resp.status_code in (200, 201) and resp_data.get("sid"):
                print(f"\n📞 [Masked Call] Successfully initiated! Call SID: {resp_data.get('sid')}")
                print(f"   Caller: {caller_e164} <---> Virtual: {twilio_number} <---> Owner: {owner_e164}\n")
                return {
                    "success": True,
                    "call_sid": resp_data.get("sid"),
                    "status": resp_data.get("status"),
                    "virtual_number": twilio_number
                }
            else:
                error_code = resp_data.get("code")
                error_msg = resp_data.get("message", resp.text)
                
                if error_code == 573002 or "verified" in error_msg.lower():
                    friendly_error = (
                        f"Twilio Trial restriction: To place calls in trial mode, numbers must be verified first. "
                        f"Go to Twilio Console -> Phone Numbers -> Manage -> 'Verified Caller IDs' and add {caller_e164}."
                    )
                elif "not assigned" in error_msg.lower() or "not a valid phone number" in error_msg.lower():
                    friendly_error = (
                        f"Twilio number {twilio_number} is not claimed or assigned in your Twilio account yet. "
                        "Click 'Get a phone number' in Twilio Console to claim your active trial number."
                    )
                else:
                    friendly_error = error_msg

                print(f"⚠️ [Twilio Voice Error] {error_msg}")
                return {
                    "success": False,
                    "error": friendly_error
                }
    except Exception as e:
        print(f"⚠️ [Twilio Voice Exception] {e}")
        return {
            "success": False,
            "error": str(e)
        }

