"""
Central definition of the API data shapes (request bodies and responses).
Field values match the database columns in models.py.
"""
import re
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------- allowed values (used by profile, portfolio and brief fields) ----------
Role = Literal["brand", "creator"]
ContentType = Literal["video", "animation", "graphic", "logo", "web", "app", "social_reel"]
Style = Literal["cinematic", "playful", "minimal", "retro", "surreal_3d", "corporate"]
AspectRatio = Literal["9:16", "16:9", "1:1", "4:5"]
LicenseType = Literal["full_commercial", "social_only", "digital_ads", "broadcast", "internal_only"]
UsageDuration = Literal["6_months", "1_year", "3_years", "perpetual"]
Territory = Literal["india", "apac", "global"]
Availability = Literal["available", "busy", "unavailable"]
EngagementStatus = Literal["sent", "accepted", "declined", "confirmed", "delivered"]


# ---------- auth ----------
class SignupIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=30, pattern=r"^[A-Za-z0-9_.]+$")
    phone: str
    password: str = Field(min_length=6)
    role: Role

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        v = re.sub(r"[\s\-()]", "", v)
        if not re.fullmatch(r"\+?\d{10,15}", v):
            raise ValueError("Phone must have 10-15 digits, optionally starting with +")
        return v


class LoginIn(BaseModel):
    email: Optional[EmailStr] = None      # log in with email...
    username: Optional[str] = None        # ...or with username
    password: str


class OtpIn(BaseModel):
    email: EmailStr
    otp: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role


class MeOut(BaseModel):
    id: int
    email: EmailStr
    username: str
    phone: str
    role: Role


# ---------- creator profile and AI portfolio ----------
class ProfileIn(BaseModel):
    display_name: str = Field(min_length=1)
    bio: str = ""
    specialization: str = ""
    rate_min: int = Field(default=0, ge=0)
    rate_max: int = Field(default=0, ge=0)
    availability: Availability = "available"
    tools: list[str] = []          # e.g. ["Sora", "Runway"]
    skills: list[str] = []         # e.g. ["Storytelling", "Color grading"]


class PortfolioIn(BaseModel):
    title: str = Field(min_length=1)
    media_url: str = ""
    thumbnail_url: str = ""
    content_type: ContentType
    is_ai_generated: bool = True   # false = human-made work
    workflow_notes: str = ""       # how the piece was made
    tools: list[str] = []          # tools used for this piece


class ToolOut(BaseModel):
    name: str
    verified: bool                 # "verified tool" badge


class BadgesOut(BaseModel):
    tools_verified: bool
    workflow_verified: bool
    past_work_verified: bool


class PortfolioItemOut(BaseModel):
    id: int
    title: str
    media_url: str
    thumbnail_url: str
    content_type: ContentType
    is_ai_generated: bool
    workflow_notes: str
    past_work_verified: bool
    tools: list[str]


class CreatorOut(BaseModel):
    id: int
    display_name: str
    bio: str
    specialization: str
    rate_min: int
    rate_max: int
    availability: Availability
    tools: list[ToolOut]
    skills: list[str]
    badges: BadgesOut
    portfolio: list[PortfolioItemOut]


class CreatorSearchOut(BaseModel):
    results: list[CreatorOut]
    total: int
    page: int
    page_size: int
    message: str = ""              # filled when there are no matches


# ---------- briefs ----------
class BriefIn(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=10)   # campaign requirements
    content_type: ContentType
    style: Style
    aspect_ratio: AspectRatio
    license_type: LicenseType                  # commercial-use requirement
    usage_duration: UsageDuration              # commercial-use requirement
    territory: Territory                       # commercial-use requirement
    platforms: list[str] = []                  # instagram, youtube, tv, website...
    budget: int = Field(gt=0)
    deadline: Optional[datetime] = None
    revisions: int = Field(default=2, ge=0, le=10)


class IdeaIn(BaseModel):
    idea: str = Field(min_length=5)            # input for the AI brief builder


class BriefOut(BriefIn):
    id: int
    brand_id: int
    status: str                                # open, in_progress, completed
    created_at: datetime


# ---------- engagements, chat and deals ----------
class EngagementIn(BaseModel):
    brief_id: int
    creator_id: int
    message: str = ""


class DecisionIn(BaseModel):
    status: Literal["accepted", "declined"]


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: int
    sender_id: int
    body: str
    created_at: datetime


class ConfirmIn(BaseModel):
    agreed_price: Optional[int] = Field(default=None, gt=0)


class DealOut(BaseModel):
    id: int
    engagement_id: int
    agreed_price: int
    license_type: LicenseType                  # copied from the brief at confirmation
    usage_duration: UsageDuration
    territory: Territory
    confirmed_at: datetime