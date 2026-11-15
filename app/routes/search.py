import re
import urllib.parse
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Depends, Query, Form, responses, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle, SearchLog, VehicleAlert
from ..auth import get_current_user, clean_vehicle_number
from ..templates_engine import templates
from ..voice import initiate_masked_call
from ..email_service import send_vehicle_alert_email
from ..sms import send_vehicle_alert_whatsapp

router = APIRouter()

def format_whatsapp_phone(phone: str) -> str:
    """Format phone number for wa.me link: only digits, defaults to 91 for 10 digit numbers."""
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        return "91" + digits
    return digits

def mask_phone_number(phone: str) -> str:
    """
    Heavily masks the phone number with asterisks for maximum on-screen privacy.
    e.g. '9876543210' -> '+91 ********10'
    """
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) >= 10:
        core = digits[-10:]
        return f"+91 ********{core[-2:]}"
    elif len(digits) >= 4:
        return f"{'*' * (len(digits) - 2)}{digits[-2:]}"
    return "**********"

@router.get("/")
def home_search(
    request: Request,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request, db)
    error = request.query_params.get("error")
    success = request.query_params.get("success")

    # If user submitted a query to search
    if q and q.strip():
        # User MUST be logged in to search owner details
        if not current_user:
            encoded_next = urllib.parse.quote(f"/search?q={q.strip()}")
            return responses.RedirectResponse(
                url=f"/login?next={encoded_next}&error=Please+sign+in+first+to+search+vehicle+owner+details.",
                status_code=status.HTTP_303_SEE_OTHER
            )

        # User is logged in -> perform search
        normalized_q = clean_vehicle_number(q)
        vehicle = db.query(Vehicle).filter(
            Vehicle.vehicle_number == normalized_q,
            Vehicle.is_active == True
        ).first()

        clean_wa_phone = ""
        masked_phone = ""
        if vehicle:
            clean_wa_phone = format_whatsapp_phone(vehicle.contact_phone)
            masked_phone = mask_phone_number(vehicle.contact_phone)

            # Log search event if someone else searches the vehicle
            if vehicle.user_id != current_user.id:
                try:
                    log_entry = SearchLog(
                        vehicle_id=vehicle.id,
                        searched_by_id=current_user.id
                    )
                    db.add(log_entry)
                    db.commit()
                except Exception:
                    db.rollback()

        return templates.TemplateResponse(
            "search.html",
            {
                "request": request,
                "current_user": current_user,
                "query": q,
                "searched": True,
                "vehicle": vehicle,
                "masked_phone": masked_phone,
                "clean_wa_phone": clean_wa_phone,
                "error": error,
                "success": success
            }
        )

    # Clean home view with search bar
    return templates.TemplateResponse(
        "search.html",
        {
            "request": request,
            "current_user": current_user,
            "query": "",
            "searched": False,
            "vehicle": None,
            "masked_phone": "",
            "clean_wa_phone": "",
            "error": error,
            "success": success
        }
    )

@router.get("/search")
def search_redirect(
    request: Request,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    return home_search(request, q, db)

# Short vehicle URL redirect: /v/DL01AB1234
@router.get("/v/{vehicle_number}")
def short_vehicle_url(
    vehicle_number: str
):
    clean_v = clean_vehicle_number(vehicle_number)
    return responses.RedirectResponse(url=f"/search?q={clean_v}", status_code=status.HTTP_303_SEE_OTHER)

# JSON API
@router.get("/api/search")
def api_search(
    request: Request,
    q: str = Query(..., description="Vehicle registration number"),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request, db)
    if not current_user:
        return responses.JSONResponse(
            status_code=401,
            content={"error": "Authentication required to search vehicle owner details."}
        )

    normalized = clean_vehicle_number(q)
    vehicle = db.query(Vehicle).filter(
        Vehicle.vehicle_number == normalized,
        Vehicle.is_active == True
    ).first()

    if not vehicle:
        return {
            "found": False,
            "query": q,
            "normalized": normalized,
            "message": "Vehicle not found"
        }

    return {
        "found": True,
        "vehicle_number": vehicle.vehicle_number,
        "masked_phone": mask_phone_number(vehicle.contact_phone),
        "notes": vehicle.notes
    }

# Masked Calling API Endpoint (Uber-style)
@router.get("/api/voice/twiml")
@router.post("/api/voice/twiml")
def get_twiml_endpoint(
    to: str = Query(...),
    caller_id: str = Query(...),
    vehicle: Optional[str] = Query("")
):
    """
    Public TwiML webhook endpoint for Twilio Voice bridging.
    """
    plate_text = f"for vehicle {vehicle}" if vehicle else ""
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="en-IN">Connecting your masked call to the vehicle owner {plate_text}. Please hold.</Say>
    <Dial callerId="{caller_id}" timeout="30">
        <Number>{to}</Number>
    </Dial>
</Response>"""
    return responses.Response(content=xml_content, media_type="application/xml")

@router.post("/api/call/mask")
def api_masked_call(
    request: Request,
    vehicle_number: str = Form(...),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request, db)
    if not current_user:
        return responses.JSONResponse(
            status_code=401,
            content={"success": False, "error": "Please sign in first to place a masked call."}
        )

    clean_v = clean_vehicle_number(vehicle_number)
    vehicle = db.query(Vehicle).filter(
        Vehicle.vehicle_number == clean_v,
        Vehicle.is_active == True
    ).first()

    if not vehicle:
        return responses.JSONResponse(
            status_code=404,
            content={"success": False, "error": "Vehicle not found or owner has paused contact."}
        )

    # Check if user is trying to call themselves
    if vehicle.user_id == current_user.id:
        return responses.JSONResponse(
            status_code=400,
            content={"success": False, "error": "This is your own registered vehicle! You cannot call yourself."}
        )

    caller_phone = current_user.phone
    owner_phone = vehicle.contact_phone

    # Initiate masked call bridging via Twilio
    result = initiate_masked_call(
        caller_phone=caller_phone,
        owner_phone=owner_phone,
        vehicle_number=clean_v
    )

    # Log search/call event
    try:
        log_entry = SearchLog(
            vehicle_id=vehicle.id,
            searched_by_id=current_user.id
        )
        db.add(log_entry)
        db.commit()
    except Exception:
        db.rollback()

    if result.get("success"):
        return {
            "success": True,
            "message": "📞 Call initiated! Pick up your ringing phone to speak with the vehicle owner.",
            "details": result
        }
    else:
        return responses.JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": result.get("error", "Failed to initiate call.")
            }
        )

# Masked Urgent Alert Endpoint (100% Free Notification Bridge)
@router.post("/api/alert/send")
def api_send_alert(
    request: Request,
    vehicle_number: str = Form(...),
    reason: str = Form(...),
    message: Optional[str] = Form(None),
    share_contact: Optional[bool] = Form(False),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request, db)
    if not current_user:
        return responses.JSONResponse(
            status_code=401,
            content={"success": False, "error": "Please sign in first to send an urgent alert."}
        )

    clean_v = clean_vehicle_number(vehicle_number)
    vehicle = db.query(Vehicle).filter(
        Vehicle.vehicle_number == clean_v,
        Vehicle.is_active == True
    ).first()

    if not vehicle:
        return responses.JSONResponse(
            status_code=404,
            content={"success": False, "error": "Vehicle not found or owner has paused contact."}
        )

    # Prevent sending alert to your own vehicle
    if vehicle.user_id == current_user.id:
        return responses.JSONResponse(
            status_code=400,
            content={"success": False, "error": "This is your own registered vehicle!"}
        )

    sender_contact_info = current_user.phone if share_contact else None

    # 1. Save alert into DB
    alert = VehicleAlert(
        vehicle_id=vehicle.id,
        sender_id=current_user.id,
        reason=reason.strip(),
        message=message.strip() if message else None,
        sender_phone=sender_contact_info
    )
    db.add(alert)

    # 2. Add SearchLog
    try:
        log_entry = SearchLog(
            vehicle_id=vehicle.id,
            searched_by_id=current_user.id
        )
        db.add(log_entry)
        db.commit()
        db.refresh(alert)
    except Exception as e:
        db.rollback()
        return responses.JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to record alert: {str(e)}"}
        )

    # 3. Dispatch Email Alert if owner email exists
    owner_user = vehicle.owner
    if owner_user and owner_user.email:
        send_vehicle_alert_email(
            to_email=owner_user.email,
            owner_name=owner_user.name,
            vehicle_number=clean_v,
            reason=reason.strip(),
            custom_message=message.strip() if message else "",
            sender_phone=sender_contact_info or ""
        )

    # 4. Dispatch WhatsApp Alert if CallMeBot or similar is configured
    if vehicle.contact_phone:
        send_vehicle_alert_whatsapp(
            phone=vehicle.contact_phone,
            vehicle_number=clean_v,
            reason=reason.strip(),
            custom_message=message.strip() if message else "",
            sender_phone=sender_contact_info or ""
        )

    return {
        "success": True,
        "message": f"🚨 Urgent alert successfully dispatched for vehicle {clean_v}! The owner has been notified on their Sampark dashboard.",
        "alert_id": alert.id,
        "clean_wa_phone": format_whatsapp_phone(vehicle.contact_phone),
        "vehicle_number": clean_v,
        "reason": reason.strip(),
        "custom_message": message.strip() if message else ""
    }


