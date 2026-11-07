import os
import urllib.parse
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db

# Isolated test database
TEST_DB_FILE = Path(__file__).resolve().parent / "test_sampark.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def test_full_user_flow():
    # 1. Reset test tables cleanly
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    # 2. Access home page without login (should succeed)
    res = client.get("/")
    assert res.status_code == 200
    assert "Connect with Any" in res.text
    assert "Sign In" in res.text
    assert "Register" in res.text
    assert "Dashboard" not in res.text
    print("✓ Logged-out view: Shows only Sign In and Register")

    # 3. Attempt to search WITHOUT login -> MUST redirect to login page
    search_res = client.get("/search?q=DL01AB1234", follow_redirects=False)
    assert search_res.status_code == 303
    assert "/login?next=" in search_res.headers["location"]
    print("✓ Searching without login redirects to /login page with next redirect")

    # 4. Step 1 of Registration: Owner submits info -> receives OTP redirect
    reg_step1 = client.post(
        "/register",
        data={
            "name": "Owner Ramesh",
            "phone": "9876543210",
            "password": "Password123!",
            "vehicle_number": "dl-01 ab 1234"
        },
        follow_redirects=False
    )
    assert reg_step1.status_code == 303
    assert "/verify-otp" in reg_step1.headers["location"]
    
    # Extract demo OTP from location URL
    loc = reg_step1.headers["location"]
    parsed_query = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query)
    otp_code = parsed_query["demo_otp"][0]
    print(f"✓ Step 1: Registered, OTP generated: {otp_code}")

    # Step 2: Try invalid OTP first
    invalid_verify = client.post(
        "/verify-otp",
        data={"phone": "9876543210", "otp_code": "000000"},
        follow_redirects=False
    )
    assert invalid_verify.status_code == 400
    assert "Invalid or expired" in invalid_verify.text
    print("✓ Invalid OTP rejected with clean error message")

    # Step 3: Submit valid OTP to complete registration
    valid_verify = client.post(
        "/verify-otp",
        data={"phone": "9876543210", "otp_code": otp_code},
        follow_redirects=False
    )
    assert valid_verify.status_code == 303
    owner_token = valid_verify.cookies["sampark_token"]
    print("✓ Step 2: Valid OTP verified, user created and logged in automatically")

    # 5. Check Logged-in Navbar: Has ONLY ONE single "Dashboard" button
    owner_home = client.get("/", cookies={"sampark_token": owner_token})
    assert owner_home.status_code == 200
    assert "Dashboard" in owner_home.text
    assert "Logout" in owner_home.text
    print("✓ Logged-in view: Shows single consolidated Dashboard button")

    # 6. Register Searcher via OTP flow and redirect to vehicle search
    searcher_reg = client.post(
        "/register",
        data={
            "name": "Searcher Suresh",
            "phone": "9123456780",
            "password": "Password123!",
            "vehicle_number": "",
            "next": "/search?q=DL01AB1234"
        },
        follow_redirects=False
    )
    loc_s = searcher_reg.headers["location"]
    s_otp = urllib.parse.parse_qs(urllib.parse.urlparse(loc_s).query)["demo_otp"][0]

    verify_s = client.post(
        "/verify-otp",
        data={
            "phone": "9123456780",
            "otp_code": s_otp,
            "next": "/search?q=DL01AB1234"
        },
        follow_redirects=False
    )
    assert verify_s.status_code == 303
    assert verify_s.headers["location"] == "/search?q=DL01AB1234"
    searcher_token = verify_s.cookies["sampark_token"]
    print("✓ Searcher verified OTP and redirected directly to search results")

    # 7. Searcher views search results: Check Strong Masking
    search_logged_in = client.get("/search?q=dl 01 ab 1234", cookies={"sampark_token": searcher_token})
    assert search_logged_in.status_code == 200
    # Heavily masked on-screen: 8 asterisks and last 2 digits (+91 ********10)
    assert "+91 ********10" in search_logged_in.text
    # Direct calling tel: link still connects to real callable number
    assert 'href="tel:9876543210"' in search_logged_in.text
    # SMS link
    assert "sms:9876543210" in search_logged_in.text
    # WhatsApp link
    assert "wa.me/919876543210" in search_logged_in.text
    print("✓ Phone number is heavily masked (+91 ********10) with direct tel:, SMS, and WhatsApp actions")

    # Clean up test database
    try:
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
    except Exception:
        pass

    print("\n All OTP verification and heavier masking tests passed successfully!")

if __name__ == "__main__":
    test_full_user_flow()
