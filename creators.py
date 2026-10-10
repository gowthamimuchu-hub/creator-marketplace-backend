from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
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

@router.get("/creators")
def search_creators(
    q: str | None = None,
    tool: list[str] | None = Query(default=None),
    skill: list[str] | None = Query(default=None),
    specialization: str | None = None,
    content_type: list[str] | None = Query(default=None),
    verified: bool = False,
    ai_only: bool = False,
    min_rate: int | None = None,
    max_rate: int | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=50),
    db: Session = Depends(get_db),
):
    query = db.query(CreatorProfile)

    if q and q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            CreatorProfile.display_name.ilike(like),
            CreatorProfile.bio.ilike(like),
            CreatorProfile.specialization.ilike(like),
            CreatorProfile.tools.any(CreatorTool.tool.has(Tool.name.ilike(like))),
            CreatorProfile.skills.any(CreatorSkill.skill.has(Skill.name.ilike(like))),
            CreatorProfile.portfolio.any(PortfolioItem.title.ilike(like)),
        ))

    if tool:  # several tools = match ANY of them
        query = query.filter(or_(*[
            CreatorProfile.tools.any(
                CreatorTool.tool.has(func.lower(Tool.name) == t.strip().lower()))
            for t in tool]))

    if skill:  # several skills = match ANY of them
        query = query.filter(or_(*[
            CreatorProfile.skills.any(
                CreatorSkill.skill.has(func.lower(Skill.name) == s.strip().lower()))
            for s in skill]))

    if specialization:
        query = query.filter(CreatorProfile.specialization.ilike(specialization.strip()))

    if content_type:
        query = query.filter(CreatorProfile.portfolio.any(
            PortfolioItem.content_type.in_([c.strip().lower() for c in content_type])))

    if ai_only:
        query = query.filter(CreatorProfile.portfolio.any(
            PortfolioItem.is_ai_generated.is_(True)))

    if verified:  # workflow verified AND at least one verified tool
        query = query.filter(
            CreatorProfile.workflow_verified.is_(True),
            CreatorProfile.tools.any(CreatorTool.is_verified.is_(True)))

    if min_rate is not None:  # creator's top rate must reach the brand's minimum
        query = query.filter(CreatorProfile.rate_max >= min_rate)
    if max_rate is not None:  # creator's lowest rate must fit the brand's maximum
        query = query.filter(CreatorProfile.rate_min <= max_rate)

    total = query.count()
    rows = (query.order_by(CreatorProfile.id)
                 .offset((page - 1) * page_size).limit(page_size).all())

    return {
        "results": [creator_out(p) for p in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "message": "" if total else "No creators match these filters. Try removing a filter.",
    }