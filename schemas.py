"""
Database Schemas for MedLink AI App

Each Pydantic model represents a MongoDB collection. The collection name is the lowercase of the class name.
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    password_hash: Optional[str] = Field(None, description="SHA256 of password for demo JWT auth")
    age: Optional[int] = Field(None, ge=0, le=120)
    gender: Optional[Literal["Male", "Female", "Other"]] = None
    is_active: bool = True
    language: Optional[str] = Field("English")
    dark_mode: bool = False
    medical_history: Optional[List[str]] = Field(default_factory=list)


class Reminder(BaseModel):
    user_email: str = Field(...)
    medicine_name: str
    time: str = Field(..., description="24h time e.g., 08:30")
    duration_days: int = Field(..., ge=1, le=365)
    notes: Optional[str] = None


class Vital(BaseModel):
    user_email: str
    heart_rate: int = Field(..., ge=20, le=220)
    bp_systolic: int = Field(..., ge=60, le=220)
    bp_diastolic: int = Field(..., ge=40, le=140)
    spo2: int = Field(..., ge=50, le=100)
    temperature_c: float = Field(..., ge=30, le=45)
    recorded_at: Optional[datetime] = None


class Doctor(BaseModel):
    name: str
    specialty: str
    status: Literal["Available", "Busy"] = "Available"
    rating: float = 4.8


class Consultation(BaseModel):
    user_email: str
    doctor_name: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    rating: Optional[int] = None


class Message(BaseModel):
    consultation_id: str
    sender: Literal["user", "doctor"]
    text: str
    sent_at: datetime


class Prescription(BaseModel):
    user_email: str
    doctor_name: str
    date: datetime
    diagnosis: str
    medicines: List[dict] = Field(..., description="List of {name, dosage, timing}")
    notes: Optional[str] = None


class OfflineMessage(BaseModel):
    user_email: Optional[str] = None
    text: str
    created_at: Optional[datetime] = None
