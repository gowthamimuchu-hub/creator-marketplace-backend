import os, random
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
TOKEN_HOURS = 24

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["auth"])


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    role: Literal["brand", "creator"]

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class OtpIn(BaseModel):
    email: EmailStr
    otp: str


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


@router.post("/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(409, "Email already registered")
    otp = f"{random.randint(0, 999999):06d}"
    user = User(
        email=body.email,
        password_hash=pwd.hash(body.password),
        role=body.role,
        is_verified=False,
        otp_code=otp,
        otp_expires=datetime.utcnow() + timedelta(minutes=10),
    )
    db.add(user)
    db.commit()
    # Hackathon shortcut: return the OTP instead of emailing it.
    return {"message": "Account created. Verify with the OTP.", "otp_demo": otp}

@router.post("/verify-otp")
def verify_otp(body: OtpIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or user.otp_code != body.otp:
        raise HTTPException(400, "Wrong OTP")
    if user.otp_expires < datetime.utcnow():
        raise HTTPException(400, "OTP expired")
    user.is_verified = True
    user.otp_code = None
    db.commit()
    return {"access_token": make_token(user), "token_type": "bearer", "role": user.role}

@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not pwd.verify(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    if not user.is_verified:
        raise HTTPException(403, "Verify your email with the OTP first")
    return {"access_token": make_token(user), "token_type": "bearer", "role": user.role}

@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}