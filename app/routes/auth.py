import random
import re
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
from ..sms import send_real_otp
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
    return templates.TemplateResponse(
        "register.html",
        {
            "request": request,
            "current_user": None,
            "prefill_vehicle": vehicle or "",
            "next_url": next or "",
            "error": error
        }
    )

@router.post("/register")
def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    vehicle_number: Optional[str] = Form(None),
    next: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    cleaned_name = name.strip()
    cleaned_email = email.strip().lower()
    cleaned_phone = phone.strip()

    # Validate email
    if not re.match(r"[^@]+@[^@]+\.[^@]+", cleaned_email):
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "current_user": None,
                "prefill_vehicle": vehicle_number or "",
                "next_url": next or "",
                "error": "Please enter a valid email address."
            },
            status_code=400
        )

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
                "error": f"An account with phone {cleaned_phone} already exists. Please sign in instead."
            },
            status_code=400
        )

    # Check if user with email already exists
    existing_email = db.query(User).filter(User.email == cleaned_email).first()
    if existing_email:
        return templates.TemplateResponse(
            "register.html",
            {
                "request": request,
                "current_user": None,
                "prefill_vehicle": vehicle_number or "",
                "next_url": next or "",
                "error": f"An account with email '{cleaned_email}' already exists. Please sign in instead."
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
                    "error": f"Vehicle plate '{clean_v_num}' is already registered by an owner."
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
        email=cleaned_email,
        otp_code=otp_code,
        name=cleaned_name,
        hashed_password=hashed,
        vehicle_number=clean_v_num if clean_v_num else None,
        expires_at=expires_at,
        is_used=False
    )
    db.add(otp_record)
    db.commit()

    # 1. Dispatch real Email OTP via Resend API
    email_res = send_real_otp_email(cleaned_email, otp_code, cleaned_name)

    # 2. Also dispatch SMS if available
    sms_res = send_real_otp(cleaned_phone, otp_code)

    is_live = email_res.get("success") or sms_res.get("success")
    next_param = f"&next={next}" if next else ""
    demo_param = f"&demo_otp={otp_code}" if not is_live else ""

    return responses.RedirectResponse(
        url=f"/verify-otp?phone={cleaned_phone}&email={cleaned_email}{demo_param}{next_param}",
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
    cleaned_phone = phone.strip()
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
                "error": "Invalid or expired verification code. Please check your inbox and try again."
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
    cleaned_phone = phone.strip()
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

    # Dispatch real Email OTP
    recip_email = latest_record.email or cleaned_email
    email_res = send_real_otp_email(recip_email, new_otp, latest_record.name)
    sms_res = send_real_otp(cleaned_phone, new_otp)

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
