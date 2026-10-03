"""
Ojas backend — FastAPI + SQLite + JWT.
Run: pip install -r requirements.txt && python main.py
API: http://localhost:8000 | Docs: http://localhost:8000/docs
Frontend continues to work offline; api.js syncs when backend is reachable.
"""
import os
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
import hashlib, secrets
from pydantic import BaseModel, EmailStr
from sqlalchemy import (create_engine, Column, Integer, String, Float, Date,
                        DateTime, ForeignKey, Text)
from sqlalchemy.orm import sessionmaker, Session, declarative_base, relationship

# ---------- config ----------
SECRET = os.getenv("OJAS_SECRET", "change-this-in-production-ojas-2026")
ALGO = "HS256"
TOKEN_DAYS = 30
DB_URL = os.getenv("OJAS_DB", "sqlite:///./ojas.db")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")  # from Google Cloud Console, see README

engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()
def _hash(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200000).hex()
    return f"{salt}${h}"
def _verify(pw: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        return secrets.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 200000).hex(), h)
    except Exception:
        return False
class _PWD:
    def hash(self, x): return _hash(x)
    def verify(self, a, b): return _verify(a, b)
pwd = _PWD()
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

# ---------- Mosaic categories (category-only, no products) ----------
CATEGORIES = {
    "man_matters": ["Hair", "Beard", "Skin", "Nutrition", "Performance", "Hygiene"],
    "be_bodywise": ["Hair", "Body Care", "Face", "Sun Protection", "Health & Fitness"],
    "little_joys": ["Nutrition", "Growth"],
    "root_labs": ["Ayurveda", "Wellness"],
}

# ---------- tables ----------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(40), default="friend")
    email = Column(String(120), unique=True, index=True)
    pw = Column(String(200))
    goal = Column(String(60), default="Deep sleep")
    dosha = Column(String(20), default="Vata")
    veg = Column(String(20), default="Veg")
    sleep_time = Column(String(10), default="23:00")
    xp = Column(Integer, default=0)
    created = Column(DateTime, default=datetime.utcnow)
    checkins = relationship("Checkin", back_populates="user", cascade="all,delete")
    habits = relationship("Habit", back_populates="user", cascade="all,delete")
    foods = relationship("Food", back_populates="user", cascade="all,delete")
    moves = relationship("Move", back_populates="user", cascade="all,delete")
    journals = relationship("Journal", back_populates="user", cascade="all,delete")

class Checkin(Base):
    __tablename__ = "checkins"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day = Column(Date, index=True)
    sleep = Column(Float, default=7); stress = Column(Float, default=3)
    mood = Column(Float, default=7); gut = Column(Float, default=7)
    score = Column(Integer, default=0)
    user = relationship("User", back_populates="checkins")

class Habit(Base):
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(120)); streak = Column(Integer, default=0)
    done_day = Column(Date, nullable=True)
    user = relationship("User", back_populates="habits")

class Food(Base):
    __tablename__ = "foods"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day = Column(Date, index=True)
    name = Column(String(160)); kcal = Column(Integer, default=0); protein = Column(Float, default=0)
    user = relationship("User", back_populates="foods")

class Move(Base):
    __tablename__ = "moves"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day = Column(Date, index=True)
    kind = Column(String(60)); minutes = Column(Integer, default=10)
    user = relationship("User", back_populates="moves")

class Water(Base):
    __tablename__ = "waters"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day = Column(Date, index=True); ml = Column(Integer, default=0)

class Journal(Base):
    __tablename__ = "journals"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    day = Column(Date, index=True); text = Column(Text)
    user = relationship("User", back_populates="journals")

Base.metadata.create_all(bind=engine)

# ---------- schemas ----------
class Signup(BaseModel):
    name: str = "friend"; email: EmailStr; password: str
    goal: str = "Deep sleep"; dosha: str = "Vata"; veg: str = "Veg"; sleep_time: str = "23:00"
class Token(BaseModel):
    access_token: str; token_type: str = "bearer"
class CheckinIn(BaseModel):
    sleep: float; stress: float; mood: float; gut: float
class HabitIn(BaseModel):
    title: str
class FoodIn(BaseModel):
    name: str; kcal: int = 0; protein: float = 0
class MoveIn(BaseModel):
    kind: str; minutes: int = 10
class WaterIn(BaseModel):
    ml: int
class JournalIn(BaseModel):
    text: str
class GoogleIn(BaseModel):
    id_token: str

# ---------- helpers ----------
def db() -> Session:
    s = SessionLocal()
    try: yield s
    finally: s.close()

def token_for(uid: int) -> str:
    exp = datetime.utcnow() + timedelta(days=TOKEN_DAYS)
    return jwt.encode({"sub": str(uid), "exp": exp}, SECRET, algorithm=ALGO)

def current(s: Session = Depends(db), t: str = Depends(oauth2)) -> User:
    try:
        uid = int(jwt.decode(t, SECRET, algorithms=[ALGO])["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    u = s.get(User, uid)
    if not u: raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User gone")
    return u

def score_of(c: CheckinIn) -> int:
    s = (30 if 7 <= c.sleep <= 9 else 22 if c.sleep >= 6 else 14 if c.sleep >= 5 else 6)
    s += (10 - c.stress) * 2.5 + c.mood * 2 + c.gut * 1.5 + 5
    return max(5, min(99, round(s)))

# ---------- app ----------
app = FastAPI(title="Ojas API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"ok": True, "time": datetime.utcnow().isoformat()}

@app.get("/categories")
def categories(): return CATEGORIES

@app.post("/auth/signup", response_model=Token)
def signup(b: Signup, s: Session = Depends(db)):
    if s.query(User).filter_by(email=b.email.lower()).first():
        raise HTTPException(400, "Email already registered")
    u = User(name=b.name[:40], email=b.email.lower(), pw=pwd.hash(b.password[:72]),
             goal=b.goal, dosha=b.dosha, veg=b.veg, sleep_time=b.sleep_time)
    s.add(u); s.commit(); s.refresh(u)
    for t in ["Jal — 8 glasses of water", "Post-dinner walk, 10 min",
              "Screens away by 11pm", "Protein at lunch", "2 min breath or pages"]:
        s.add(Habit(user_id=u.id, title=t))
    s.commit()
    return Token(access_token=token_for(u.id))

@app.post("/auth/login", response_model=Token)
def login(f: OAuth2PasswordRequestForm = Depends(), s: Session = Depends(db)):
    u = s.query(User).filter_by(email=f.username.lower()).first()
    if not u or not pwd.verify(f.password, u.pw):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return Token(access_token=token_for(u.id))

@app.post("/auth/google", response_model=Token)
def google_login(b: GoogleIn, s: Session = Depends(db)):
    """Verify Google ID token (from Google Identity Services), find/create user, return our JWT."""
    try:
        from google.oauth2 import id_token as gid_token
        from google.auth.transport import requests as grequests
        info = gid_token.verify_oauth2_token(b.id_token, grequests.Request(),
                                             GOOGLE_CLIENT_ID or None)
        email = (info.get("email") or "").lower()
        if not email or not info.get("email_verified", True):
            raise HTTPException(400, "Google email not verified")
        if GOOGLE_CLIENT_ID and info.get("aud") != GOOGLE_CLIENT_ID:
            raise HTTPException(400, "Token audience mismatch")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Invalid Google token")
    u = s.query(User).filter_by(email=email).first()
    if not u:
        u = User(name=(info.get("name") or email.split("@")[0])[:40],
                 email=email, pw="google-oauth",
                 goal="Deep sleep", dosha="Vata", veg="Veg", sleep_time="23:00")
        s.add(u); s.commit(); s.refresh(u)
        for title in ["Jal — 8 glasses of water", "Post-dinner walk, 10 min",
                      "Screens away by 11pm", "Protein at lunch", "2 min breath or pages"]:
            s.add(Habit(user_id=u.id, title=title))
        s.commit()
    return Token(access_token=token_for(u.id))

@app.get("/me")
def me(u: User = Depends(current)):
    return {"name": u.name, "email": u.email, "goal": u.goal, "dosha": u.dosha,
            "veg": u.veg, "sleep_time": u.sleep_time, "xp": u.xp}

@app.post("/checkins")
def save_checkin(b: CheckinIn, u: User = Depends(current), s: Session = Depends(db)):
    d = date.today()
    c = s.query(Checkin).filter_by(user_id=u.id, day=d).first() or Checkin(user_id=u.id, day=d)
    c.sleep, c.stress, c.mood, c.gut, c.score = b.sleep, b.stress, b.mood, b.gut, score_of(b)
    s.add(c); u.xp += 10; s.commit()
    return {"day": str(d), "score": c.score, "xp": u.xp}

@app.get("/checkins/week")
def week(u: User = Depends(current), s: Session = Depends(db)):
    out = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        c = s.query(Checkin).filter_by(user_id=u.id, day=d).first()
        out.append({"day": str(d), "score": c.score if c else None,
                    "sleep": c.sleep if c else None})
    return out

@app.get("/habits")
def list_habits(u: User = Depends(current), s: Session = Depends(db)):
    return [{"id": h.id, "title": h.title, "streak": h.streak,
             "done_today": h.done_day == date.today()}
            for h in s.query(Habit).filter_by(user_id=u.id).all()]

@app.post("/habits")
def add_habit(b: HabitIn, u: User = Depends(current), s: Session = Depends(db)):
    h = Habit(user_id=u.id, title=b.title[:120]); s.add(h); s.commit(); s.refresh(h)
    return {"id": h.id, "title": h.title}

@app.post("/habits/{hid}/toggle")
def toggle(hid: int, u: User = Depends(current), s: Session = Depends(db)):
    h = s.query(Habit).filter_by(id=hid, user_id=u.id).first()
    if not h: raise HTTPException(404, "Habit not found")
    if h.done_day == date.today(): h.done_day = None
    else: h.done_day = date.today(); h.streak += 1; u.xp += 5
    s.commit()
    return {"done_today": h.done_day == date.today(), "streak": h.streak, "xp": u.xp}

@app.post("/food")
def log_food(b: FoodIn, u: User = Depends(current), s: Session = Depends(db)):
    s.add(Food(user_id=u.id, day=date.today(), name=b.name[:160], kcal=b.kcal, protein=b.protein))
    u.xp += 2; s.commit(); return {"xp": u.xp}

@app.get("/food/today")
def food_today(u: User = Depends(current), s: Session = Depends(db)):
    rows = s.query(Food).filter_by(user_id=u.id, day=date.today()).all()
    return {"items": [{"name": r.name, "kcal": r.kcal, "protein": r.protein} for r in rows],
            "kcal": sum(r.kcal for r in rows), "protein": round(sum(r.protein for r in rows), 1)}

@app.post("/water")
def log_water(b: WaterIn, u: User = Depends(current), s: Session = Depends(db)):
    w = s.query(Water).filter_by(user_id=u.id, day=date.today()).first() or Water(user_id=u.id, day=date.today(), ml=0)
    w.ml += b.ml; s.add(w); s.commit(); return {"ml": w.ml}

@app.post("/moves")
def log_move(b: MoveIn, u: User = Depends(current), s: Session = Depends(db)):
    s.add(Move(user_id=u.id, day=date.today(), kind=b.kind[:60], minutes=b.minutes))
    u.xp += 5; s.commit(); return {"xp": u.xp}

@app.post("/journal")
def log_journal(b: JournalIn, u: User = Depends(current), s: Session = Depends(db)):
    s.add(Journal(user_id=u.id, day=date.today(), text=b.text[:500]))
    u.xp += 5; s.commit(); return {"xp": u.xp}

@app.get("/insights")
def insights(u: User = Depends(current), s: Session = Depends(db)):
    days = [(date.today() - timedelta(days=i)) for i in range(6, -1, -1)]
    scores = [ (c.score if (c := s.query(Checkin).filter_by(user_id=u.id, day=d).first()) else None) for d in days ]
    valid = [x for x in scores if x is not None]
    return {"week": [{"day": str(d), "score": sc} for d, sc in zip(days, scores)],
            "avg": round(sum(valid)/len(valid)) if valid else None,
            "xp": u.xp,
            "message": "Seal today's check-in to begin." if not valid else
                       ("Fix the sleep hour first — everything follows." if sum(valid)/len(valid) < 55 else "Luminous rhythm. Guard it.")}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
