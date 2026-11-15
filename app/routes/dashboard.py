import io
import qrcode
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, responses, status, Response, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle, SearchLog, VehicleAlert
from ..auth import require_login, clean_vehicle_number, get_current_user
from ..templates_engine import templates

router = APIRouter()

@router.get("/dashboard")
def dashboard_view(
    request: Request,
    db: Session = Depends(get_db)
):
    current_user = require_login(request, db)
    vehicles = db.query(Vehicle).filter(
        Vehicle.user_id == current_user.id
    ).order_by(Vehicle.created_at.desc()).all()

    # Fetch recent lookup logs and urgent alerts for all vehicles owned by this user
    vehicle_ids = [v.id for v in vehicles]
    recent_alerts = []
    active_alerts = []
    all_vehicle_alerts = []

    if vehicle_ids:
        # Search lookups
        recent_alerts = db.query(SearchLog).filter(
            SearchLog.vehicle_id.in_(vehicle_ids)
        ).order_by(SearchLog.created_at.desc()).limit(10).all()

        # Urgent vehicle alerts
        all_vehicle_alerts = db.query(VehicleAlert).filter(
            VehicleAlert.vehicle_id.in_(vehicle_ids)
        ).order_by(VehicleAlert.created_at.desc()).limit(20).all()

        active_alerts = [a for a in all_vehicle_alerts if not a.is_resolved]

    error = request.query_params.get("error")
    success = request.query_params.get("success")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "vehicles": vehicles,
            "recent_alerts": recent_alerts,
            "active_alerts": active_alerts,
            "all_vehicle_alerts": all_vehicle_alerts,
            "error": error,
            "success": success
        }
    )

@router.post("/dashboard/alert/resolve/{alert_id}")
def resolve_alert(
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    current_user = require_login(request, db)
    alert = db.query(VehicleAlert).join(Vehicle).filter(
        VehicleAlert.id == alert_id,
        Vehicle.user_id == current_user.id
    ).first()

    if alert:
        alert.is_resolved = True
        db.commit()
        return responses.RedirectResponse(
            url="/dashboard?success=Alert+marked+as+resolved!",
            status_code=status.HTTP_303_SEE_OTHER
        )

    return responses.RedirectResponse(
        url="/dashboard?error=Alert+not+found.",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/api/alerts/live")
def get_live_alerts(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Real-time polling endpoint for in-app alert popups and mobile push notifications.
    """
    current_user = get_current_user(request, db)
    if not current_user:
        return {"logged_in": False, "alerts": []}

    vehicles = db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()
    v_ids = [v.id for v in vehicles]
    if not v_ids:
        return {"logged_in": True, "alerts": []}

    unresolved_alerts = db.query(VehicleAlert).filter(
        VehicleAlert.vehicle_id.in_(v_ids),
        VehicleAlert.is_resolved == False
    ).order_by(VehicleAlert.created_at.desc()).limit(5).all()

    alert_list = []
    for a in unresolved_alerts:
        alert_list.append({
            "id": a.id,
            "vehicle_number": a.vehicle.vehicle_number if a.vehicle else "",
            "reason": a.reason,
            "message": a.message or "",
            "sender_phone": a.sender_phone or "",
            "created_at": a.created_at.strftime("%I:%M %p")
        })

    return {"logged_in": True, "alerts": alert_list}

@router.post("/api/alert/resolve")
def api_resolve_alert(
    request: Request,
    alert_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """
    AJAX endpoint to mark an alert as resolved directly from the in-app popup.
    """
    current_user = get_current_user(request, db)
    if not current_user:
        return responses.JSONResponse(status_code=401, content={"success": False, "error": "Not logged in"})

    alert = db.query(VehicleAlert).join(Vehicle).filter(
        VehicleAlert.id == alert_id,
        Vehicle.user_id == current_user.id
    ).first()

    if alert:
        alert.is_resolved = True
        db.commit()
        return {"success": True, "message": "Alert marked as resolved"}

    return responses.JSONResponse(status_code=404, content={"success": False, "error": "Alert not found"})

@router.post("/api/alert/respond")
def api_respond_alert(
    request: Request,
    alert_id: int = Form(...),
    response_text: str = Form(...),
    mark_resolved: bool = Form(False),
    db: Session = Depends(get_db)
):
    """
    Owner clicks 'On my way in 2 mins' or 'Moving car now' -> saves response so searcher sees it live.
    """
    current_user = get_current_user(request, db)
    if not current_user:
        return responses.JSONResponse(status_code=401, content={"success": False, "error": "Not logged in"})

    alert = db.query(VehicleAlert).join(Vehicle).filter(
        VehicleAlert.id == alert_id,
        Vehicle.user_id == current_user.id
    ).first()

    if alert:
        alert.owner_response = response_text.strip()
        if mark_resolved:
            alert.is_resolved = True
        db.commit()
        return {"success": True, "message": "Response recorded", "owner_response": alert.owner_response}

    return responses.JSONResponse(status_code=404, content={"success": False, "error": "Alert not found"})

@router.get("/api/alert/status/{alert_id}")
def api_check_alert_status(
    alert_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Public live polling endpoint for the searcher: shows when owner replies or resolves alert!
    """
    alert = db.query(VehicleAlert).filter(VehicleAlert.id == alert_id).first()
    if not alert:
        return {"found": False}

    return {
        "found": True,
        "id": alert.id,
        "is_resolved": alert.is_resolved,
        "owner_response": alert.owner_response or ""
    }

@router.post("/dashboard/vehicle/add")
def add_vehicle(
    request: Request,
    vehicle_number: str = Form(...),
    contact_phone: str = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    current_user = require_login(request, db)
    clean_v_num = clean_vehicle_number(vehicle_number)

    if not clean_v_num:
        return responses.RedirectResponse(
            url="/dashboard?error=Please+enter+a+valid+vehicle+plate+number.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Check if vehicle number already registered
    existing_vehicle = db.query(Vehicle).filter(Vehicle.vehicle_number == clean_v_num).first()
    if existing_vehicle:
        return responses.RedirectResponse(
            url=f"/dashboard?error=Vehicle+{clean_v_num}+is+already+registered.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    # Add vehicle
    vehicle = Vehicle(
        user_id=current_user.id,
        vehicle_number=clean_v_num,
        contact_phone=contact_phone.strip(),
        notes=notes.strip() if notes else None
    )
    db.add(vehicle)
    db.commit()

    return responses.RedirectResponse(
        url=f"/dashboard?success=Vehicle+{clean_v_num}+added+successfully!",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/dashboard/vehicle/edit/{vehicle_id}")
def edit_vehicle(
    vehicle_id: int,
    request: Request,
    contact_phone: str = Form(...),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    current_user = require_login(request, db)

    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.user_id == current_user.id
    ).first()

    if not vehicle:
        return responses.RedirectResponse(
            url="/dashboard?error=Vehicle+not+found+or+permission+denied.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    vehicle.contact_phone = contact_phone.strip()
    vehicle.notes = notes.strip() if notes else None
    db.commit()

    return responses.RedirectResponse(
        url=f"/dashboard?success=Vehicle+{vehicle.vehicle_number}+updated+successfully!",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/dashboard/vehicle/toggle/{vehicle_id}")
def toggle_vehicle_status(
    vehicle_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    current_user = require_login(request, db)

    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.user_id == current_user.id
    ).first()

    if not vehicle:
        return responses.RedirectResponse(
            url="/dashboard?error=Vehicle+not+found.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    vehicle.is_active = not vehicle.is_active
    db.commit()

    status_str = "activated" if vehicle.is_active else "paused (hidden from search)"
    return responses.RedirectResponse(
        url=f"/dashboard?success=Vehicle+{vehicle.vehicle_number}+{status_str}.",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/dashboard/vehicle/delete/{vehicle_id}")
def delete_vehicle(
    vehicle_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    current_user = require_login(request, db)

    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.user_id == current_user.id
    ).first()

    if not vehicle:
        return responses.RedirectResponse(
            url="/dashboard?error=Vehicle+not+found+or+permission+denied.",
            status_code=status.HTTP_303_SEE_OTHER
        )

    v_num = vehicle.vehicle_number
    db.delete(vehicle)
    db.commit()

    return responses.RedirectResponse(
        url=f"/dashboard?success=Vehicle+{v_num}+removed+successfully.",
        status_code=status.HTTP_303_SEE_OTHER
    )

# Windshield Sticker Page
@router.get("/sticker/{vehicle_number}")
def view_sticker(
    vehicle_number: str,
    request: Request,
    db: Session = Depends(get_db)
):
    clean_v_num = clean_vehicle_number(vehicle_number)
    vehicle = db.query(Vehicle).filter(
        Vehicle.vehicle_number == clean_v_num
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return templates.TemplateResponse(
        "sticker.html",
        {
            "request": request,
            "vehicle": vehicle
        }
    )

# High-Res QR Code Image Stream
@router.get("/qr/{vehicle_number}")
def generate_qr(
    vehicle_number: str,
    request: Request,
    db: Session = Depends(get_db)
):
    clean_v_num = clean_vehicle_number(vehicle_number)
    vehicle = db.query(Vehicle).filter(
        Vehicle.vehicle_number == clean_v_num
    ).first()

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    base_url = str(request.base_url).rstrip("/")
    target_url = f"{base_url}/search?q={clean_v_num}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")
