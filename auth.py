import os, re, random
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from database import get_db
from models import User

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_HOURS = 24

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["auth"])


# ---------- request bodies ----------
class SignupIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.]+$")
    phone: str
    password: str = Field(min_length=6)
    role: Literal["brand", "creator"]

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        v = re.sub(r"[\s\-()]", "", v)
        if not re.fullmatch(r"\+?\d{10,15}", v):
            raise ValueError("Phone must have 10-15 digits, optionally starting with +")
        return v


class LoginIn(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str


class OtpIn(BaseModel):
    email: EmailStr
    otp: str


# ---------- helpers ----------
def make_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    try:
        data = jwt.decode(cred.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user = db.get(User, int(data["sub"]))
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, "Invalid or expired token")
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_role(role: str):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role != role:
            raise HTTPException(403, f"Only {role}s can do this")
        return user
    return checker


# ---------- routes ----------
@router.post("/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "Email already registered")
    if db.query(User).filter(User.username.ilike(body.username)).first():
        raise HTTPException(409, "Username already taken")
    otp = f"{random.randint(0, 999999):06d}"
    user = User(
        email=body.email,
        username=body.username,
        phone=body.phone,
        password_hash=pwd.hash(body.password),
        role=body.role,
        is_verified=False,
        otp_code=otp,
        otp_expires=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(user)
    db.commit()
    # Hackathon shortcut: return the OTP instead of emailing or texting it.
    return {"message": "Account created. Verify with the OTP.", "otp_demo": otp}


@router.post("/verify-otp")
def verify_otp(body: OtpIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not user.otp_code or user.otp_code != body.otp:
        raise HTTPException(400, "Wrong OTP")
    if user.otp_expires < datetime.utcnow():
        raise HTTPException(400, "OTP expired")
    user.is_verified = True
    user.otp_code = None
    db.commit()
    return {"access_token": make_token(user), "token_type": "bearer", "role": user.role}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    if not body.email and not body.username:
        raise HTTPException(422, "Provide an email or a username")
    q = db.query(User)
    user = (q.filter(User.email == body.email).first() if body.email
            else q.filter(User.username.ilike(body.username)).first())
    if not user or not pwd.verify(body.password, user.password_hash):
        raise HTTPException(401, "Wrong login details or password")
    if not user.is_verified:
        raise HTTPException(403, "Verify your account with the OTP first")
    return {"access_token": make_token(user), "token_type": "bearer", "role": user.role}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "phone": user.phone,
        "role": user.role,
    }