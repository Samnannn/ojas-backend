# Ojas Backend

FastAPI + SQLite + JWT. No API keys needed to run.

## Run
```
cd backend
pip install -r requirements.txt
python main.py
```
API at http://localhost:8000, docs at http://localhost:8000/docs

## Endpoints
- GET /health, GET /categories (Mosaic category-only data)
- POST /auth/signup {name,email,password,goal,dosha,veg,sleep_time}
- POST /auth/login (OAuth2 form: username=email, password)
- POST /auth/google {id_token} — Google Sign-In (verify + auto-create user)
- GET /me, POST /checkins, GET /checkins/week
- GET/POST /habits, POST /habits/{id}/toggle
- POST /food, GET /food/today, POST /water, POST /moves, POST /journal
- GET /insights

## Env
- OJAS_SECRET — change in production
- OJAS_DB — default sqlite:///./ojas.db
- GOOGLE_CLIENT_ID — required to enforce Google audience check (else any valid Google token accepted)

## Google Sign-In setup (one time, ~5 min)
1. Go to console.cloud.google.com → New Project (e.g. Ojas) → APIs & Services → Credentials.
2. Configure OAuth consent screen (External, app name Ojas, your email) → Save.
3. Credentials → Create Credentials → OAuth client ID → Web application.
4. Authorized JavaScript origins: add http://localhost:8000 and your Netlify/Vercel frontend URL.
5. Copy the Client ID (ends with .apps.googleusercontent.com).
6. Backend: set env GOOGLE_CLIENT_ID to it (locally: setx GOOGLE_CLIENT_ID "paste" or export).
7. Frontend: click G Sign-in once and paste the same Client ID when prompted (stored in browser), or run OjasAPI.setGoogleClient("paste").
8. Click G Sign-in again → Google popup → backend verifies via POST /auth/google → cloud linked. No client secret needed anywhere.

## Deploy (free)
- Render: New Web Service → point to backend/, start `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Then in the app console: `OjasAPI.setBase("https://your-api.onrender.com")`
- Frontend stays static (Netlify/Vercel/GitHub Pages).

## Frontend
`../ojas-app/api.js` auto-detects the backend. Offline = localStorage only. Online + logged in = check-ins also sync to cloud. Nothing breaks if backend is down.
