# 🚀 Deploying on Vercel & Sending REAL SMS OTPs

This guide walks you through deploying to **Vercel** and receiving **REAL SMS OTPs** on your mobile phone.

---

## 📱 Part 1: How to Send REAL SMS OTP to Your Phone

To send real text messages to an Indian mobile phone, an SMS Gateway API key is required. We have pre-integrated **Fast2SMS** (the easiest and most popular in India, offering free trial credits upon signup).

### Step-by-Step Setup:
1. Go to **[fast2sms.com](https://www.fast2sms.com/)** and create a free account.
2. Once signed in, look at the left sidebar and click on **Dev API**.
3. Copy your **API Authorization Key** (e.g. `AB1234cd56EF...`).
4. Open your [`.env`](file:///c:/Users/dell6/OneDrive/Desktop/Sampark2.0/.env) file and add this line:
   ```env
   FAST2SMS_API_KEY="your_copied_api_key_here"
   ```
5. Save the file and restart your app (`python run.py`).
6. Register with your real mobile number — **a real SMS will arrive on your phone within seconds!**

*(Note: Twilio is also supported by adding `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER` into `.env`).*

---

## ☁️ Part 2: How to Deploy on Vercel (1-Click)

The project now includes [`vercel.json`](file:///c:/Users/dell6/OneDrive/Desktop/Sampark2.0/vercel.json) and [`api/index.py`](file:///c:/Users/dell6/OneDrive/Desktop/Sampark2.0/api/index.py), making it 100% ready for Vercel.

### Step 1: Push Project to GitHub
In your PowerShell terminal in the `Sampark2.0` folder:
```powershell
git init
git add .
git commit -m "Sampark 2.0 with Supabase and Real OTP ready"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/sampark.git
git push -u origin main
```

### Step 2: Import into Vercel
1. Go to **[vercel.com](https://vercel.com/)** and sign in (with your GitHub account).
2. Click **"Add New..."** &rarr; **"Project"**.
3. Find your `sampark` repository and click **"Import"**.
4. In the **Environment Variables** section, expand it and add:
   * **`DATABASE_URL`**: Your Supabase connection string:
     ```text
     postgresql://postgres.pmbzostkdeirgllahszn:Vraj%4025030405@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres
     ```
   * **`FAST2SMS_API_KEY`**: *(Your Fast2SMS API key for real SMS OTP)*
   * **`SECRET_KEY`**: `sampark-super-secure-production-key-2026`
5. Click **"Deploy"**!

Within ~45 seconds, Vercel will assign you a live production URL like:
👉 **`https://sampark-xyz.vercel.app`**

Anyone anywhere in the world will be able to access your site, search vehicle plates, receive real OTPs on their phone, and initiate direct calls!

