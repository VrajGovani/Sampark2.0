# 📱 Testing on Phone & Deploying Sampark 2.0

This guide explains how to test direct calling on your phone right now, where data is saved, and how to scale with **Supabase**.

---

## 1. 📍 Where is Data Stored Right Now?

All your users, vehicle records, hashed passwords, and OTP records are stored in a single persistent file on your computer:
* **File path**: `Sampark2.0/sampark.db` (SQLite)
* **How to view it**: You can open this file using [DB Browser for SQLite](https://sqlitebrowser.org/) or any SQLite extension to see your records directly.

---

## 2. 📱 How to Test Calling on Your Phone Right Now (Immediate Wi-Fi Access)

`run.py` has been configured to listen on all network interfaces (`0.0.0.0`) and automatically detect your Wi-Fi IP address.

1. Make sure your **Mobile Phone** and **Computer** are connected to the same Wi-Fi.
2. In your terminal, run:
   ```powershell
   python run.py
   ```
3. Look at the output in the console. It will display:
   ```
   💻 On your PC browser:   http://localhost:8000
   📱 On your MOBILE PHONE:  http://10.119.52.146:8000
   ```
4. Open `http://10.119.52.146:8000` (or the IP shown) in your **phone's Chrome or Safari browser**.
5. Search any registered vehicle plate:
   * Tap **Call Directly** &rarr; your phone's dialer will immediately pop up with the real number ready to call!
   * Tap **WhatsApp** &rarr; opens the official WhatsApp app with the vehicle's pre-composed emergency message.
   * Tap **Text SMS** &rarr; opens your phone's default SMS app.

---

## 3. 🌐 Test via Free Public HTTPS Link (Cellular Data / Anywhere)

If your phone is on cellular data (4G/5G) rather than Wi-Fi:

### Option A: Cloudflare Tunnel (Free, no account needed)
1. Download `cloudflared.exe` from Cloudflare or run:
   ```powershell
   winget install Cloudflare.cloudflared
   ```
2. Start your app in one terminal:
   ```powershell
   python run.py
   ```
3. Run this in a second terminal:
   ```powershell
   cloudflared tunnel --url http://localhost:8000
   ```
4. It will give you a public URL like `https://random-words.trycloudflare.com` that you can open from any phone anywhere in the world!

---

## 4. ⚡ Scaling Up with Supabase (PostgreSQL)

If you want a production-grade, highly scalable cloud database:

1. Create a free project on [Supabase](https://supabase.com).
2. Go to **Project Settings &rarr; Database &rarr; Connection String &rarr; URI**.
3. Copy the URI (it looks like `postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres`).
4. Set the environment variable in your terminal:
   * **PowerShell**:
     ```powershell
     $env:DATABASE_URL="postgresql://postgres:[YOUR_PASSWORD]@db.[YOUR_REF].supabase.co:5432/postgres"
     ```
   * **CMD**:
     ```cmd
     set DATABASE_URL=postgresql://postgres:[YOUR_PASSWORD]@db.[YOUR_REF].supabase.co:5432/postgres
     ```
5. Run `python run.py`.
   * **Sampark will automatically detect Supabase**, create all tables (`users`, `vehicles`, `otp_verifications`, `search_logs`), and run on Supabase with **zero code modifications**!

---

## 5. 🚀 Deploying to the Cloud (Render / Railway)

1. Push this project to a GitHub repository:
   ```bash
   git init
   git add .
   git commit -m "Sampark 2.0 MVP ready"
   git branch -M main
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```
2. Go to [Render.com](https://render.com) or [Railway.app](https://railway.app):
   * Click **New &rarr; Web Service**.
   * Connect your GitHub repo.
   * Set **Build Command**: `pip install -r requirements.txt`
   * Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   * Under **Environment Variables**, add:
     * `DATABASE_URL` = *(Your Supabase connection string)*
     * `SECRET_KEY` = *(Any secure random string)*
3. Click **Deploy**. Your app will be live on a custom `.onrender.com` or custom domain with free SSL!

