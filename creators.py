from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import (User, CreatorProfile, Tool, Skill, CreatorTool, CreatorSkill,
                    PortfolioItem, PortfolioItemTool)
from auth import require_role

router = APIRouter(tags=["creators"])

ContentType = Literal["video", "animation", "graphic", "logo", "web", "app", "social_reel"]


# ---------- request bodies ----------
class ProfileIn(BaseModel):
    display_name: str = Field(min_length=1)
    bio: str = ""
    specialization: str = ""
    rate_min: int = Field(default=0, ge=0)
    rate_max: int = Field(default=0, ge=0)
    availability: Literal["available", "busy", "unavailable"] = "available"
    tools: list[str] = []
    skills: list[str] = []


class PortfolioIn(BaseModel):
    title: str = Field(min_length=1)
    media_url: str = ""
    thumbnail_url: str = ""
    content_type: ContentType
    is_ai_generated: bool = True
    workflow_notes: str = ""
    tools: list[str] = []


# ---------- helpers ----------
def get_or_create(db: Session, model, name: str):
    name = name.strip()
    obj = db.query(model).filter(model.name.ilike(name)).first()
    if not obj:
        obj = model(name=name)
        db.add(obj)
        db.flush()
    return obj


def item_out(i: PortfolioItem) -> dict:
    return {
        "id": i.id,
        "title": i.title,
        "media_url": i.media_url,
        "thumbnail_url": i.thumbnail_url,
        "content_type": i.content_type,
        "is_ai_generated": i.is_ai_generated,
        "workflow_notes": i.workflow_notes,
        "past_work_verified": i.past_work_verified,
        "tools": [t.tool.name for t in i.tools],
    }


def creator_out(p: CreatorProfile) -> dict:
    return {
        "id": p.id,
        "display_name": p.display_name,
        "bio": p.bio,
        "specialization": p.specialization,
        "rate_min": p.rate_min,
        "rate_max": p.rate_max,
        "availability": p.availability,
        "tools": [{"name": t.tool.name, "verified": t.is_verified} for t in p.tools],
        "skills": [s.skill.name for s in p.skills],
        "badges": {
            "tools_verified": any(t.is_verified for t in p.tools),
            "workflow_verified": p.workflow_verified,
            "past_work_verified": any(i.past_work_verified for i in p.portfolio),
        },
        "portfolio": [item_out(i) for i in p.portfolio],
    }


def my_profile(db: Session, user: User) -> CreatorProfile:
    p = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    if not p:
        raise HTTPException(404, "Create your profile first (PUT /creators/me)")
    return p


# ---------- routes ----------
@router.put("/creators/me")
def save_my_profile(body: ProfileIn,
                    user: User = Depends(require_role("creator")),
                    db: Session = Depends(get_db)):
    if body.rate_max and body.rate_max < body.rate_min:
        raise HTTPException(422, "rate_max must be >= rate_min")

    p = db.query(CreatorProfile).filter(CreatorProfile.user_id == user.id).first()
    if not p:
        p = CreatorProfile(user_id=user.id, display_name=body.display_name)
        db.add(p)
        db.flush()

    p.display_name = body.display_name
    p.bio = body.bio
    p.specialization = body.specialization
    p.rate_min = body.rate_min
    p.rate_max = body.rate_max
    p.availability = body.availability

    # tools: keep the verified flag for tools that stay on the profile
    old = {t.tool.name.lower(): t.is_verified for t in p.tools}
    p.tools.clear()
    db.flush()
    for name in {n.strip() for n in body.tools if n.strip()}:
        tool = get_or_create(db, Tool, name)
        p.tools.append(CreatorTool(tool_id=tool.id,
                                   is_verified=old.get(tool.name.lower(), False)))

    p.skills.clear()
    db.flush()
    for name in {n.strip() for n in body.skills if n.strip()}:
        skill = get_or_create(db, Skill, name)
        p.skills.append(CreatorSkill(skill_id=skill.id))

    db.commit()
    db.refresh(p)
    return creator_out(p)


@router.get("/creators/me")
def read_my_profile(user: User = Depends(require_role("creator")),
                    db: Session = Depends(get_db)):
    return creator_out(my_profile(db, user))


@router.get("/creators/{creator_id}")
def get_creator(creator_id: int, db: Session = Depends(get_db)):
    p = db.get(CreatorProfile, creator_id)
    if not p:
        raise HTTPException(404, "Creator not found")
    return creator_out(p)


@router.post("/portfolio", status_code=201)
def add_portfolio_item(body: PortfolioIn,
                       user: User = Depends(require_role("creator")),
                       db: Session = Depends(get_db)):
    p = my_profile(db, user)
    item = PortfolioItem(
        creator_id=p.id,
        title=body.title,
        media_url=body.media_url,
        thumbnail_url=body.thumbnail_url,
        content_type=body.content_type,
        is_ai_generated=body.is_ai_generated,
        workflow_notes=body.workflow_notes,
    )
    for name in {n.strip() for n in body.tools if n.strip()}:
        tool = get_or_create(db, Tool, name)
        item.tools.append(PortfolioItemTool(tool_id=tool.id))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item_out(item)


@router.delete("/portfolio/{item_id}")
def delete_portfolio_item(item_id: int,
                          user: User = Depends(require_role("creator")),
                          db: Session = Depends(get_db)):
    p = my_profile(db, user)
    item = db.get(PortfolioItem, item_id)
    if not item or item.creator_id != p.id:
        raise HTTPException(404, "Portfolio item not found")
    db.delete(item)
    db.commit()
    return {"deleted": item_id}


@router.get("/tools")
def list_tools(db: Session = Depends(get_db)):
    return [t.name for t in db.query(Tool).order_by(Tool.name)]


@router.get("/skills")
def list_skills(db: Session = Depends(get_db)):
    return [s.name for s in db.query(Skill).order_by(Skill.name)]