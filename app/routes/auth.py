import random
import re
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, Query, responses, status
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User, Vehicle, OTPVerification
from ..auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    clean_vehicle_number,
)
from ..sms import send_real_otp, clean_phone_for_sms
from ..email_service import send_real_otp_email

router = APIRouter()
TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

def is_safe_redirect(url: Optional[str]) -> bool:
    """Ensure redirect URL starts with / and not // to prevent open redirect vulnerabilities."""
    return bool(url and url.startswith("/") and not url.startswith("//"))

def mask_phone_for_display(phone: str) -> str:
    cleaned = (phone or "").strip()
    if len(cleaned) >= 4:
        return f"+91 ********{cleaned[-2:]}"
    return "+91 **********"

def mask_email_for_display(email: str) -> str:
    cleaned = (email or "").strip().lower()
    if not cleaned or "@" not in cleaned:
        return ""
    user_part, domain_part = cleaned.split("@", 1)
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain_part}"

def get_firebase_config() -> dict:
    """Loads Firebase Web configuration from environment variables."""
    return {
        "apiKey": os.getenv("FIREBASE_API_KEY", "").strip(),
        "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", "").strip(),
        "projectId": os.getenv("FIREBASE_PROJECT_ID", "").strip(),
        "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET", "").strip(),
        "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID", "").strip(),
        "appId": os.getenv("FIREBASE_APP_ID", "").strip()
    }

# Phone availability pre-check for Firebase Phone Auth
@router.get("/api/check-phone")
def api_check_phone(
    phone: str = Query(...),
    db: Session = Depends(get_db)
):
    clean = clean_phone_for_sms(phone)
    if not clean or len(clean) != 10:
        return {"valid": False, "error": "Please enter a valid 10-digit Indian mobile number."}

    user = db.query(User).filter(User.phone == clean).first()
    if user:
        return {"valid": False, "error": f"An account with phone +91 {clean} already exists. Please sign in instead."}

    return {"valid": True, "clean_phone": clean}

# Firebase Verified Registration Endpoint
@router.post("/api/register/firebase-complete")
def firebase_register_complete(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    vehicle_number: Optional[str] = Form(None),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    cleaned_name = name.strip()
    cleaned_phone = clean_phone_for_sms(phone)

    if not cleaned_phone or len(cleaned_phone) != 10:
        return responses.JSONResponse(status_code=400, content={"success": False, "error": "Invalid 10-digit mobile number."})

    existing_user = db.query(User).filter(User.phone == cleaned_phone).first()
    if existing_user:
        return responses.JSONResponse(status_code=400, content={"success": False, "error": f"An account with phone +91 {cleaned_phone} already exists."})

    clean_v_num = clean_vehicle_number(vehicle_number) if vehicle_number else ""
    if clean_v_num:
        existing_vehicle = db.query(Vehicle).filter(Vehicle.vehicle_number == clean_v_num).first()
        if existing_vehicle:
            return responses.JSONResponse(status_code=400, content={"success": False, "error": f"Vehicle plate '{clean_v_num}' is already registered."})

    hashed = hash_password(password)
    new_user = User(
        name=cleaned_name,
        phone=cleaned_phone,
        hashed_password=hashed,
        is_phone_verified=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    if clean_v_num:
        v_rec = Vehicle(
            user_id=new_user.id,
            vehicle_number=clean_v_num,
            contact_phone=cleaned_phone,
            notes="Default registration"
        )
        db.add(v_rec)
        db.commit()

    token = create_access_token({"user_id": new_user.id, "phone": new_user.phone})
    target = next if is_safe_redirect(next) else "/dashboard?success=Phone+verified+via+Google+SMS!+Welcome+to+Sampark."
    
    resp = responses.JSONResponse(content={"success": True, "redirect_url": target})
    resp.set_cookie(
        key="sampark_token",
        value=token,
        httponly=True,
        max_age=30 * 86400,
        samesite="lax"
    )
    return resp

@router.get("/login")
def login_page(
    request: Request,
    next: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request, db)
    if current_user:
        target = next if is_safe_redirect(next) else "/dashboard"
        return responses.RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)

    error = request.query_params.get("error")
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "current_user": None,
            "next_url": next or "",
            "error": error
        }
    )

@router.post("/login")
def login_submit(
    request: Request,
    phone: str = Form(...),  # Accepts phone number OR email
    password: str = Form(...),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    identifier = phone.strip()
    
    # Allow logging in with phone or email
    user = db.query(User).filter(
        (User.phone == identifier) | (User.email == identifier.lower())
    ).first()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "current_user": None,
                "next_url": next or "",
                "error": "Invalid phone number / email or password. Please try again."
            },
            status_code=400
        )

    # Issue session token
    token = create_access_token({"user_id": user.id, "phone": user.phone})
    target = next if is_safe_redirect(next) else "/dashboard?success=Welcome+back!"
    response = responses.RedirectResponse(
        url=target,
        status_code=status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        key="sampark_token",
        value=token,
        httponly=True,
        max_age=30 * 86400,
        samesite="lax"
    )
    return response

@router.get("/register")
def register_page(
    request: Request,
    vehicle: Optional[str] = None,
    next: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    current_user = get_current_user(request, db)
    if current_user:
        target = next if is_safe_redirect(next) else "/dashboard"
        return responses.RedirectResponse(url=target, status_code=status.HTTP_303_SEE_OTHER)

    error = request.query_params.get("error")
    firebase_cfg = get_firebase_config()

    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "current_user": None,
            "prefill_vehicle": vehicle or "",
            "next_url": next or "",
            "error": error,
            "firebase_config": firebase_cfg,
            "has_firebase": bool(firebase_cfg.get("apiKey"))
        }
    )

@router.post("/register")
def register_submit(
    request: Request,
    name: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    email: Optional[str] = Form(None),
    vehicle_number: Optional[str] = Form(None),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    cleaned_name = name.strip()
    cleaned_phone = clean_phone_for_sms(phone)
    cleaned_email = (email or "").strip().lower()

    # Check if user with phone already exists
    existing_phone = db.query(User).filter(User.phone == cleaned_phone).first()
    if existing_phone:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "current_user": None,
                "prefill_vehicle": vehicle_number or "",
                "next_url": next or "",
                "error": f"An account with phone {cleaned_phone} already exists. Please sign in instead.",
                "firebase_config": get_firebase_config(),
                "has_firebase": bool(get_firebase_config().get("apiKey"))
            },
            status_code=400
        )

    clean_v_num = clean_vehicle_number(vehicle_number) if vehicle_number else ""
    if clean_v_num:
        existing_vehicle = db.query(Vehicle).filter(Vehicle.vehicle_number == clean_v_num).first()
        if existing_vehicle:
            return templates.TemplateResponse(
                "register.html",
                {
                    "request": request,
                    "current_user": None,
                    "prefill_vehicle": vehicle_number,
                    "next_url": next or "",
                    "error": f"Vehicle plate '{clean_v_num}' is already registered by an owner.",
                    "firebase_config": get_firebase_config(),
                    "has_firebase": bool(get_firebase_config().get("apiKey"))
                },
                status_code=400
            )

    # Generate 6-Digit OTP
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    hashed = hash_password(password)

    # Store OTP verification record
    otp_record = OTPVerification(
        phone=cleaned_phone,
        email=cleaned_email if cleaned_email else None,
        otp_code=otp_code,
        name=cleaned_name,
        hashed_password=hashed,
        vehicle_number=clean_v_num if clean_v_num else None,
        expires_at=expires_at,
        is_used=False
    )
    db.add(otp_record)
    db.commit()

    # Dispatch via SMS / Email
    sms_res = send_real_otp(cleaned_phone, otp_code)
    email_res = {"success": False}
    if cleaned_email:
        email_res = send_real_otp_email(cleaned_email, otp_code, cleaned_name)

    is_live = email_res.get("success") or sms_res.get("success")
    next_param = f"&next={next}" if next else ""
    demo_param = f"&demo_otp={otp_code}" if not is_live else ""
    email_param = f"&email={cleaned_email}" if cleaned_email else ""

    return responses.RedirectResponse(
        url=f"/verify-otp?phone={cleaned_phone}{email_param}{demo_param}{next_param}",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/verify-otp")
def verify_otp_page(
    request: Request,
    phone: str = Query(...),
    email: Optional[str] = Query(None),
    demo_otp: Optional[str] = Query(None),
    next: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    error = request.query_params.get("error")
    success = request.query_params.get("success")

    return templates.TemplateResponse(
        "verify_otp.html",
        {
            "request": request,
            "current_user": None,
            "phone": phone,
            "email": email or "",
            "masked_phone": mask_phone_for_display(phone),
            "masked_email": mask_email_for_display(email) if email else "",
            "demo_otp": demo_otp,
            "next_url": next or "",
            "error": error,
            "success": success
        }
    )

@router.post("/verify-otp")
def verify_otp_submit(
    request: Request,
    phone: str = Form(...),
    email: Optional[str] = Form(None),
    otp_code: str = Form(...),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    cleaned_phone = clean_phone_for_sms(phone)
    cleaned_email = (email or "").strip().lower()
    cleaned_otp = otp_code.strip()

    # Find the latest unexpired and unused OTP record matching phone or email
    query = db.query(OTPVerification).filter(
        OTPVerification.otp_code == cleaned_otp,
        OTPVerification.is_used == False,
        OTPVerification.expires_at >= datetime.utcnow()
    )
    if cleaned_email:
        query = query.filter((OTPVerification.phone == cleaned_phone) | (OTPVerification.email == cleaned_email))
    else:
        query = query.filter(OTPVerification.phone == cleaned_phone)

    record = query.order_by(OTPVerification.created_at.desc()).first()

    if not record:
        return templates.TemplateResponse(
            "verify_otp.html",
            {
                "request": request,
                "current_user": None,
                "phone": cleaned_phone,
                "email": cleaned_email,
                "masked_phone": mask_phone_for_display(cleaned_phone),
                "masked_email": mask_email_for_display(cleaned_email),
                "demo_otp": None,
                "next_url": next or "",
                "error": "Invalid or expired verification code. Please check and try again."
            },
            status_code=400
        )

    # Mark OTP as used
    record.is_used = True

    # Create the verified user
    new_user = User(
        name=record.name,
        phone=record.phone,
        email=record.email,
        hashed_password=record.hashed_password,
        is_phone_verified=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # If vehicle number was attached, create vehicle
    if record.vehicle_number:
        vehicle_record = Vehicle(
            user_id=new_user.id,
            vehicle_number=record.vehicle_number,
            contact_phone=record.phone,
            notes="Default registration"
        )
        db.add(vehicle_record)
        db.commit()

    # Issue session token
    token = create_access_token({"user_id": new_user.id, "phone": new_user.phone})
    target = next if is_safe_redirect(next) else "/dashboard?success=Account+verified!+Welcome+to+Sampark."
    response = responses.RedirectResponse(
        url=target,
        status_code=status.HTTP_303_SEE_OTHER
    )
    response.set_cookie(
        key="sampark_token",
        value=token,
        httponly=True,
        max_age=30 * 86400,
        samesite="lax"
    )
    return response

@router.post("/resend-otp")
def resend_otp(
    request: Request,
    phone: str = Form(...),
    email: Optional[str] = Form(None),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    cleaned_phone = clean_phone_for_sms(phone)
    cleaned_email = (email or "").strip().lower()

    query = db.query(OTPVerification)
    if cleaned_email:
        query = query.filter((OTPVerification.phone == cleaned_phone) | (OTPVerification.email == cleaned_email))
    else:
        query = query.filter(OTPVerification.phone == cleaned_phone)

    latest_record = query.order_by(OTPVerification.created_at.desc()).first()

    if not latest_record:
        return responses.RedirectResponse(url="/register", status_code=status.HTTP_303_SEE_OTHER)

    new_otp = f"{random.randint(100000, 999999)}"
    latest_record.otp_code = new_otp
    latest_record.expires_at = datetime.utcnow() + timedelta(minutes=10)
    latest_record.is_used = False
    db.commit()

    # Dispatch real SMS / Email
    sms_res = send_real_otp(cleaned_phone, new_otp)
    email_res = {"success": False}
    recip_email = latest_record.email or cleaned_email
    if recip_email:
        email_res = send_real_otp_email(recip_email, new_otp, latest_record.name)

    is_live = email_res.get("success") or sms_res.get("success")
    demo_param = f"&demo_otp={new_otp}" if not is_live else ""
    next_param = f"&next={next}" if next else ""
    email_param = f"&email={recip_email}" if recip_email else ""

    return responses.RedirectResponse(
        url=f"/verify-otp?phone={cleaned_phone}{email_param}{demo_param}{next_param}&success=New+verification+code+sent!",
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/logout")
def logout():
    response = responses.RedirectResponse(url="/?success=Signed+out+successfully.", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="sampark_token")
    return response
