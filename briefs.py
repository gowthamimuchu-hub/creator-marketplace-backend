from datetime import datetime
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User, Brief
from auth import require_role

router = APIRouter(prefix="/briefs", tags=["briefs"])

ContentType = Literal["video", "animation", "graphic", "logo", "web", "app", "social_reel"]
Style = Literal["cinematic", "playful", "minimal", "retro", "surreal_3d", "corporate"]
AspectRatio = Literal["9:16", "16:9", "1:1", "4:5"]
LicenseType = Literal["full_commercial", "social_only", "digital_ads", "broadcast", "internal_only"]
Duration = Literal["6_months", "1_year", "3_years", "perpetual"]
Territory = Literal["india", "apac", "global"]

OPTIONS = {
    "content_type": list(ContentType.__args__),
    "style": list(Style.__args__),
    "aspect_ratio": list(AspectRatio.__args__),
    "license_type": list(LicenseType.__args__),
    "usage_duration": list(Duration.__args__),
    "territory": list(Territory.__args__),
    "platforms": ["instagram", "youtube", "tv", "website", "app_store", "print"],
}


class BriefIn(BaseModel):
    title: str = Field(min_length=3)
    description: str = Field(min_length=10)
    content_type: ContentType
    style: Style
    aspect_ratio: AspectRatio
    license_type: LicenseType
    usage_duration: Duration
    territory: Territory
    platforms: list[str] = []
    budget: int = Field(gt=0)
    deadline: Optional[datetime] = None
    revisions: int = Field(default=2, ge=0, le=10)


class IdeaIn(BaseModel):
    idea: str = Field(min_length=5)


def brief_out(b: Brief) -> dict:
    return {
        "id": b.id,
        "brand_id": b.brand_id,
        "title": b.title,
        "description": b.description,
        "content_type": b.content_type,
        "style": b.style,
        "aspect_ratio": b.aspect_ratio,
        "license_type": b.license_type,
        "usage_duration": b.usage_duration,
        "territory": b.territory,
        "platforms": [p for p in (b.platforms or "").split(",") if p],
        "budget": b.budget,
        "deadline": b.deadline.isoformat() if b.deadline else None,
        "revisions": b.revisions,
        "status": b.status,
        "created_at": b.created_at.isoformat(),
    }


# Fixed paths (/options, /generate) must come BEFORE /{brief_id}
@router.get("/options")
def brief_options():
    """Dropdown values for the frontend brief form."""
    return OPTIONS


@router.post("/generate")
def generate_brief(body: IdeaIn, user: User = Depends(require_role("brand"))):
    """Bonus: turn a rough idea into a structured brief (rule-based for now)."""
    t = body.idea.lower()
    has = lambda *words: any(w in t for w in words)

    content_type = ("logo" if has("logo") else
                    "social_reel" if has("reel", "short", "instagram", "tiktok") else
                    "animation" if has("animat", "mascot") else
                    "graphic" if has("poster", "banner", "graphic") else
                    "web" if has("website", "landing") else
                    "app" if has("app") else "video")
    style = ("cinematic" if has("cinemat", "film") else
             "playful" if has("fun", "playful", "bright", "cute") else
             "minimal" if has("minimal", "clean") else
             "retro" if has("retro", "vintage") else
             "surreal_3d" if has("surreal", "3d", "dream") else "corporate")
    ratio = ("9:16" if has("reel", "short", "instagram", "tiktok", "story") else
             "16:9" if has("youtube", "tv", "film", "website") else
             "4:5" if has("poster") else "1:1")
    lic = ("broadcast" if has("tv", "broadcast") else
           "social_only" if has("instagram", "social", "reel", "tiktok") else
           "digital_ads" if has("ad ", "ads", "campaign") else "full_commercial")
    platforms = [p for p, kw in [("instagram", "instagram"), ("youtube", "youtube"),
                                 ("tv", " tv"), ("website", "website")] if kw in t]

    return {
        "title": body.idea.strip().capitalize()[:60],
        "description": f"Goal: {body.idea.strip()}. Deliverables: 1 hero asset plus 2 cutdowns. "
                       "Share the AI tools and workflow used with the final delivery.",
        "content_type": content_type,
        "style": style,
        "aspect_ratio": ratio,
        "license_type": lic,
        "usage_duration": "1_year",
        "territory": "global" if has("global", "worldwide") else "india",
        "platforms": platforms,
        "budget": 30000,
        "revisions": 2,
        "note": "Draft generated from your idea. Review every field before sending.",
    }


@router.post("", status_code=201)
def create_brief(body: BriefIn,
                 user: User = Depends(require_role("brand")),
                 db: Session = Depends(get_db)):
    b = Brief(
        brand_id=user.id,
        title=body.title,
        description=body.description,
        content_type=body.content_type,
        style=body.style,
        aspect_ratio=body.aspect_ratio,
        license_type=body.license_type,
        usage_duration=body.usage_duration,
        territory=body.territory,
        platforms=",".join(p.strip().lower() for p in body.platforms if p.strip()),
        budget=body.budget,
        deadline=body.deadline,
        revisions=body.revisions,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return brief_out(b)


@router.get("")
def my_briefs(user: User = Depends(require_role("brand")),
              db: Session = Depends(get_db)):
    rows = (db.query(Brief).filter(Brief.brand_id == user.id)
              .order_by(Brief.id.desc()).all())
    return {"results": [brief_out(b) for b in rows], "total": len(rows)}


@router.get("/{brief_id}")
def get_brief(brief_id: int,
              user: User = Depends(require_role("brand")),
              db: Session = Depends(get_db)):
    b = db.get(Brief, brief_id)
    if not b or b.brand_id != user.id:
        raise HTTPException(404, "Brief not found")
    return brief_out(b)