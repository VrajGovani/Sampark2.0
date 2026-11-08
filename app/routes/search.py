import re
import urllib.parse
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Depends, Query, responses, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle, SearchLog
from ..auth import get_current_user, clean_vehicle_number
from ..templates_engine import templates

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
