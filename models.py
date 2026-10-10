from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, Boolean, DateTime,
                        Float, ForeignKey, UniqueConstraint)
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)              # "brand" or "creator"
    is_verified = Column(Boolean, default=False)
    otp_code = Column(String, nullable=True)
    otp_expires = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    profile = relationship("CreatorProfile", back_populates="user", uselist=False)


class Tool(Base):
    __tablename__ = "tools"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)  # Sora, Runway...


class Skill(Base):
    __tablename__ = "skills"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)


class CreatorProfile(Base):
    __tablename__ = "creator_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    display_name = Column(String, nullable=False)
    bio = Column(Text, default="")
    specialization = Column(String, index=True)         # AI Filmmaking, AI Animation...
    rate_min = Column(Integer, default=0)
    rate_max = Column(Integer, default=0)
    availability = Column(String, default="available")
    workflow_verified = Column(Boolean, default=False)  # workflow badge

    user = relationship("User", back_populates="profile")
    tools = relationship("CreatorTool", cascade="all, delete-orphan")
    skills = relationship("CreatorSkill", cascade="all, delete-orphan")
    portfolio = relationship("PortfolioItem", cascade="all, delete-orphan")


class CreatorTool(Base):
    __tablename__ = "creator_tools"
    __table_args__ = (UniqueConstraint("creator_id", "tool_id"),)
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey("creator_profiles.id"))
    tool_id = Column(Integer, ForeignKey("tools.id"))
    is_verified = Column(Boolean, default=False)        # tool badge
    tool = relationship("Tool")


class CreatorSkill(Base):
    __tablename__ = "creator_skills"
    __table_args__ = (UniqueConstraint("creator_id", "skill_id"),)
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey("creator_profiles.id"))
    skill_id = Column(Integer, ForeignKey("skills.id"))
    skill = relationship("Skill")


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    id = Column(Integer, primary_key=True)
    creator_id = Column(Integer, ForeignKey("creator_profiles.id"))
    title = Column(String, nullable=False)
    media_url = Column(String, default="")
    thumbnail_url = Column(String, default="")
    content_type = Column(String, index=True)           # video, animation, graphic, logo, web, app
    is_ai_generated = Column(Boolean, default=True)
    workflow_notes = Column(Text, default="")
    past_work_verified = Column(Boolean, default=False) # past-work badge
    tools = relationship("PortfolioItemTool", cascade="all, delete-orphan")


class PortfolioItemTool(Base):
    __tablename__ = "portfolio_item_tools"
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("portfolio_items.id"))
    tool_id = Column(Integer, ForeignKey("tools.id"))
    tool = relationship("Tool")


class Brief(Base):
    __tablename__ = "briefs"
    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey("users.id"), index=True)
    title = Column(String, nullable=False)
    description = Column(Text, default="")
    content_type = Column(String)                       # video, animation, graphic...
    style = Column(String)
    aspect_ratio = Column(String)                       # 9:16, 16:9, 1:1, 4:5
    license_type = Column(String)                       # full, social_only, digital_ads, broadcast, internal
    usage_duration = Column(String)                     # 6_months, 1_year, 3_years, perpetual
    territory = Column(String)                          # india, global, apac
    platforms = Column(String, default="")              # comma-separated
    budget = Column(Integer, default=0)
    deadline = Column(DateTime, nullable=True)
    revisions = Column(Integer, default=2)
    status = Column(String, default="open")
    created_at = Column(DateTime, default=datetime.utcnow)


class Engagement(Base):
    __tablename__ = "engagements"
    id = Column(Integer, primary_key=True)
    brief_id = Column(Integer, ForeignKey("briefs.id"))
    creator_id = Column(Integer, ForeignKey("creator_profiles.id"))
    status = Column(String, default="sent")             # sent, accepted, declined, confirmed, delivered
    created_at = Column(DateTime, default=datetime.utcnow)
    brief = relationship("Brief")
    creator = relationship("CreatorProfile")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    engagement_id = Column(Integer, ForeignKey("engagements.id"), index=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Deal(Base):
    __tablename__ = "deals"
    id = Column(Integer, primary_key=True)
    engagement_id = Column(Integer, ForeignKey("engagements.id"), unique=True)
    agreed_price = Column(Integer, default=0)
    license_type = Column(String)                       # copied from the brief
    usage_duration = Column(String)
    territory = Column(String)
    confirmed_at = Column(DateTime, default=datetime.utcnow)