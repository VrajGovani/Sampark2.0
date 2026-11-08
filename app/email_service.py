import os
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Load .env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

def send_real_otp_email(to_email: str, otp_code: str, user_name: str = "") -> dict:
    """
    Sends a 6-digit verification code to the recipient's email address via Resend API.
    Resend free tier gives 3,000 emails/month, 100/day with 100% instant inbox delivery.
    """
    cleaned_email = (to_email or "").strip().lower()
    if not cleaned_email:
        return {"success": False, "error": "No recipient email provided"}

    subject = f"🔐 Your Sampark Verification Code: {otp_code}"
    display_name = user_name.strip() if user_name else "Vehicle Owner"

    html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Sampark 2.0 Verification</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="padding: 40px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 480px; background-color: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
          <!-- Header -->
          <tr>
            <td style="background-color: #0f172a; padding: 28px 32px; text-align: center;">
              <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;">🚗 Sampark 2.0</h1>
              <p style="margin: 6px 0 0; color: #94a3b8; font-size: 13px;">Vehicle Contact & Safety Directory</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 32px;">
              <h2 style="margin: 0 0 12px; color: #0f172a; font-size: 18px; font-weight: 700;">Verify Your Email Address</h2>
              <p style="margin: 0 0 20px; color: #475569; font-size: 14px; line-height: 1.6;">
                Hi <b>{display_name}</b>,<br>
                Thank you for joining Sampark. Use the 6-digit verification code below to verify your account:
              </p>
              
              <!-- OTP Box -->
              <div style="background-color: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #2563eb; font-family: monospace;">{otp_code}</span>
              </div>

              <p style="margin: 0 0 16px; color: #64748b; font-size: 13px; line-height: 1.5;">
                ⏰ This code is valid for <b>10 minutes</b>. Never share this code with anyone.
              </p>
              <p style="margin: 0; color: #94a3b8; font-size: 12px;">
                If you did not request this verification code, you can safely ignore this email.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px; text-align: center;">
              <p style="margin: 0; color: #94a3b8; font-size: 11px;">
                &copy; 2026 Sampark 2.0. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    resend_api_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_api_key:
        try:
            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": "Sampark 2.0 <onboarding@resend.dev>",
                "to": [cleaned_email],
                "subject": subject,
                "html": html_content
            }
            with httpx.Client(timeout=10) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code in (200, 201):
                    print(f"\n✅ [Resend] Real OTP email successfully delivered to {cleaned_email}!\n")
                    return {"success": True, "provider": "Resend", "details": resp.json()}
                else:
                    print(f"⚠️ [Resend Error] HTTP {resp.status_code}: {resp.text}")
                    return {"success": False, "provider": "Resend", "error": resp.text}
        except Exception as e:
            print(f"⚠️ [Resend Exception] {e}")
            return {"success": False, "provider": "Resend", "error": str(e)}

    # Fallback when key not yet added
    print("\n" + "=" * 55)
    print(f"📧 [TEST MODE] Generated Email OTP for {cleaned_email}: {otp_code}")
    print(f"   (Add RESEND_API_KEY in .env to receive real emails in inbox)")
    print("=" * 55 + "\n")
    return {"success": False, "provider": "Console", "demo": True}

