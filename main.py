import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

from database import create_document, get_documents, db
from schemas import User, Reminder, Vital, Doctor, Consultation, Message, Prescription, OfflineMessage

JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_change_me")
JWT_ALGO = "HS256"

app = FastAPI(title="MedLink AI App API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------- Auth Helpers ----------------------
http_bearer = HTTPBearer(auto_error=False)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: Optional[str] = None
    email: Optional[str] = None


def create_token(email: str, name: str = "User") -> str:
    payload = {
        "sub": email,
        "name": name,
        "exp": datetime.utcnow() + timedelta(days=7),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer)) -> Optional[dict]:
    if not creds:
        return None
    token = creds.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        return {"email": payload.get("sub"), "name": payload.get("name")}
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------------------- Basic & Health ----------------------
@app.get("/")
def root():
    return {"app": "MedLink AI", "status": "ok"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Set"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# ---------------------- Auth Endpoints ----------------------
class LoginRequest(BaseModel):
    email: str
    name: Optional[str] = "User"
    password: Optional[str] = None  # demo only


@app.post("/auth/login", response_model=TokenResponse)
def login(req: LoginRequest):
    # Demo: accept any email/password and return token
    token = create_token(req.email, req.name or "User")
    return TokenResponse(access_token=token, name=req.name, email=req.email)


@app.post("/auth/guest", response_model=TokenResponse)
def guest_login():
    email = "guest@medlink.ai"
    token = create_token(email, "Guest")
    return TokenResponse(access_token=token, name="Guest", email=email)


# ---------------------- Symptom Checker ----------------------
class SymptomRequest(BaseModel):
    text: str


KEYWORDS: Dict[str, List[str]] = {
    "Viral Fever": ["fever", "chills", "body ache", "fatigue"],
    "COVID-19": ["loss of taste", "loss of smell", "dry cough", "shortness of breath"],
    "Typhoid": ["high fever", "abdominal pain", "constipation", "rose spots"],
    "Common Cold": ["runny nose", "sneezing", "sore throat"],
    "Migraine": ["headache", "throbbing", "sensitivity to light"],
}


@app.post("/ai/analyze")
def analyze_symptoms(req: SymptomRequest):
    text = req.text.lower()
    matches = []
    for diagnosis, keys in KEYWORDS.items():
        if any(k in text for k in keys):
            matches.append(diagnosis)
    if not matches:
        matches = ["General Viral Infection", "Dehydration"]
    return {"possible_causes": matches[:3]}


# ---------------------- Doctors & Consultation ----------------------
@app.get("/doctors", response_model=List[Doctor])
def list_doctors():
    seed = [
        {"name": "Dr. Neha Kapoor", "specialty": "General Physician", "status": "Available", "rating": 4.9},
        {"name": "Dr. Arjun Mehta", "specialty": "Cardiologist", "status": "Busy", "rating": 4.7},
        {"name": "Dr. Ishita Rao", "specialty": "Pediatrician", "status": "Available", "rating": 4.8},
    ]
    return seed


class StartCallRequest(BaseModel):
    user_email: str
    doctor_name: str


@app.post("/consult/start")
def start_consult(req: StartCallRequest):
    cons = Consultation(
        user_email=req.user_email,
        doctor_name=req.doctor_name,
        started_at=datetime.utcnow(),
    )
    cons_id = create_document("consultation", cons)
    return {"consultation_id": cons_id, "status": "started"}


class ChatMessage(BaseModel):
    consultation_id: str
    sender: str
    text: str


@app.post("/consult/message")
def post_message(msg: ChatMessage):
    message = Message(
        consultation_id=msg.consultation_id,
        sender="user" if msg.sender not in ["user", "doctor"] else msg.sender,
        text=msg.text,
        sent_at=datetime.utcnow(),
    )
    _id = create_document("message", message)
    return {"message_id": _id}


class EndCallRequest(BaseModel):
    consultation_id: str
    rating: Optional[int] = None


@app.post("/consult/end")
def end_consult(req: EndCallRequest):
    # For demo, just echo. In real app, update consultation with rating/end time
    return {"consultation_id": req.consultation_id, "status": "ended", "rating": req.rating}


# ---------------------- Prescriptions ----------------------
@app.get("/prescriptions/sample", response_model=Prescription)
def get_sample_prescription():
    return Prescription(
        user_email="sandhya@example.com",
        doctor_name="Dr. Neha Kapoor",
        date=datetime.utcnow(),
        diagnosis="Viral Fever",
        medicines=[
            {"name": "Paracetamol 500mg", "dosage": "1 tablet", "timing": "Every 6 hours"},
            {"name": "ORS", "dosage": "200ml", "timing": "After each loose stool"},
        ],
        notes="Hydrate well and rest for 2-3 days."
    )


# ---------------------- Reminders ----------------------
@app.post("/reminders")
def create_reminder(rem: Reminder, user: Optional[dict] = Depends(get_current_user)):
    _ = create_document("reminder", rem)
    return {"status": "created"}


@app.get("/reminders")
def list_reminders(email: Optional[str] = None):
    docs = get_documents("reminder", {"user_email": email} if email else {}, limit=100)
    # convert ObjectId to str
    for d in docs:
        d["_id"] = str(d["_id"]) if "_id" in d else None
    return docs


# ---------------------- Vitals ----------------------
@app.post("/vitals")
def record_vital(v: Vital):
    _ = create_document("vital", v)
    return {"status": "recorded"}


@app.get("/vitals")
def get_vitals(email: Optional[str] = None, limit: int = 20):
    docs = get_documents("vital", {"user_email": email} if email else {}, limit=limit)
    for d in docs:
        d["_id"] = str(d["_id"]) if "_id" in d else None
    return docs


# ---------------------- Offline / SMS Mode ----------------------
@app.post("/offline")
def save_offline(msg: OfflineMessage):
    _ = create_document("offlinemessage", msg)
    return {"status": "queued", "info": "A doctor will reply via SMS soon."}


# ---------------------- Profile ----------------------
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    language: Optional[str] = None
    dark_mode: Optional[bool] = None


@app.get("/profile")
def get_profile(email: str = "sandhya@example.com"):
    # For prototype, return a mock profile
    return {
        "name": "Sandhya",
        "email": email,
        "age": 28,
        "gender": "Female",
        "language": "English",
        "dark_mode": False,
        "medical_history": ["Consultation - 2024-05-10", "Typhoid (2019)"]
    }


@app.post("/profile")
def update_profile(update: ProfileUpdate):
    # For prototype, just echo back
    return {"status": "updated", "profile": update.model_dump(exclude_none=True)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
