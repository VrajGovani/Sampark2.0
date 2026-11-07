import socket
import uvicorn

def get_local_ip():
    """Detect local Wi-Fi / LAN IP so you can test on your phone."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("\n" + "=" * 60)
    print("🚀 Sampark 2.0 Server is LIVE & Ready for Phone Testing!")
    print(f"💻 On your PC browser:   http://localhost:8000")
    print(f"📱 On your MOBILE PHONE:  http://{local_ip}:8000")
    print("   👉 Make sure your phone is connected to the same Wi-Fi")
    print(f"📖 API Documentation:    http://localhost:8000/docs")
    print("=" * 60 + "\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
