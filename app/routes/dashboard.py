import io
import qrcode
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, responses, status, Response, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Vehicle, SearchLog
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

    # Fetch recent lookup alerts for all vehicles owned by this user
    vehicle_ids = [v.id for v in vehicles]
    recent_alerts = []
    if vehicle_ids:
        recent_alerts = db.query(SearchLog).filter(
            SearchLog.vehicle_id.in_(vehicle_ids)
        ).order_by(SearchLog.created_at.desc()).limit(10).all()

    error = request.query_params.get("error")
    success = request.query_params.get("success")

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "vehicles": vehicles,
            "recent_alerts": recent_alerts,
            "error": error,
            "success": success
        }
    )

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
