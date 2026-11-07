# Sampark 2.0 - Vehicle Contact Directory 🚗📞

A Python & FastAPI application inspired by [sampark.me/search](https://sampark.me/search). It allows vehicle owners to register their vehicle plate numbers along with their contact phone numbers. Anyone can search any vehicle plate without logging in to reach the owner directly (useful for blocked parking, emergencies, flat tires, or open windows).

---

## 🛠 Tech Stack

- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.13)
- **Database**: SQLite (built-in, with SQLAlchemy ORM) &rarr; ready to switch to PostgreSQL
- **Frontend**: Server-rendered Jinja2 Templates + Tailwind CSS (via CDN) + Lucide Icons
- **Authentication**: JWT Cookie session auth + `bcrypt` password hashing
- **Server**: Uvicorn ASGI server

---

## ✨ Features Built in This MVP

1. **Public Vehicle Search (No Login Required)**:
   - Visitors land on `/` and can immediately enter any vehicle registration number (e.g. `DL 01 AB 1234` or `MH 12 XY 9999`).
   - Normalizes input (ignores spaces, hyphens, lowercase) so matches are accurate.
   - If found:
     - Displays owner's contact number prominently.
     - Quick action buttons: **Call Directly** (`tel:`), **WhatsApp Message**, and **Copy Number**.
     - Displays optional owner notes (e.g., parking instructions).
   - If not found:
     - Displays a helpful alert with a direct prompt for the owner to register.

2. **Separate Owner Portal (Add / Manage Vehicles)**:
   - **Sign Up / Sign In**: Phone number + password authentication.
   - **Owner Dashboard**:
     - Add new vehicles with customizable contact numbers and emergency notes.
     - View all registered vehicles.
     - One-click "Preview Lookup" to test what visitors see when searching.
     - Remove / manage registered vehicles.

3. **REST API Endpoint**:
   - `GET /api/search?q=DL01AB1234` returns JSON for future mobile apps or integrations.

---

## 🚀 How to Run

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the Web Application**:
   ```bash
   python run.py
   ```

3. **Open in Browser**:
   - Web App: [http://127.0.0.1:8000](http://127.0.0.1:8000)
   - Interactive API Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

4. **Run Integration Tests**:
   ```bash
   python test_flow.py
   ```

