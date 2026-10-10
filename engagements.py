from datetime import datetime
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models import User, Brief, CreatorProfile, Engagement, Message, Deal
from auth import get_current_user, require_role
from briefs import brief_out

router = APIRouter(prefix="/engagements", tags=["engagements"])


# ---------- request bodies ----------
class EngagementIn(BaseModel):
    brief_id: int
    creator_id: int                      # CreatorProfile.id
    message: str = ""                    # optional first message

class DecisionIn(BaseModel):
    status: Literal["accepted", "declined"]

class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

class ConfirmIn(BaseModel):
    agreed_price: Optional[int] = Field(default=None, gt=0)


# ---------- helpers ----------
def deal_out(d: Deal) -> dict:
    return {
        "id": d.id, "engagement_id": d.engagement_id, "agreed_price": d.agreed_price,
        "license_type": d.license_type, "usage_duration": d.usage_duration,
        "territory": d.territory, "confirmed_at": d.confirmed_at.isoformat(),
    }

def engagement_out(e: Engagement, db: Session) -> dict:
    deal = db.query(Deal).filter(Deal.engagement_id == e.id).first()
    return {
        "id": e.id,
        "status": e.status,
        "created_at": e.created_at.isoformat(),
        "brief": brief_out(e.brief),
        "creator": {"id": e.creator.id, "display_name": e.creator.display_name,
                    "specialization": e.creator.specialization},
        "deal": deal_out(deal) if deal else None,
    }

def message_out(m: Message) -> dict:
    return {"id": m.id, "sender_id": m.sender_id, "body": m.body,
            "created_at": m.created_at.isoformat()}

def load_engagement(db: Session, eid: int, user: User) -> Engagement:
    """Fetch an engagement and make sure this user is the brand or the creator on it."""
    e = db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "Engagement not found")
    if user.id not in (e.brief.brand_id, e.creator.user_id):
        raise HTTPException(404, "Engagement not found")   # hide existence
    return e


# ---------- routes ----------
@router.post("", status_code=201)
def send_brief(body: EngagementIn,
               user: User = Depends(require_role("brand")),
               db: Session = Depends(get_db)):
    brief = db.get(Brief, body.brief_id)
    if not brief or brief.brand_id != user.id:
        raise HTTPException(404, "Brief not found")
    creator = db.get(CreatorProfile, body.creator_id)
    if not creator:
        raise HTTPException(404, "Creator not found")
    if creator.availability == "unavailable":
        raise HTTPException(409, "This creator is not taking new work")
    existing = (db.query(Engagement)
                  .filter(Engagement.brief_id == brief.id,
                          Engagement.creator_id == creator.id,
                          Engagement.status.in_(["sent", "accepted", "confirmed"])).first())
    if existing:
        raise HTTPException(409, "You already sent this brief to this creator")

    e = Engagement(brief_id=brief.id, creator_id=creator.id, status="sent")
    db.add(e)
    db.flush()
    if body.message.strip():
        db.add(Message(engagement_id=e.id, sender_id=user.id, body=body.message.strip()))
    db.commit()
    db.refresh(e)
    return engagement_out(e, db)


@router.get("")
def my_engagements(user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Brand: engagements on their briefs. Creator: briefs sent to them."""
    q = db.query(Engagement)
    if user.role == "brand":
        q = q.join(Brief, Engagement.brief_id == Brief.id).filter(Brief.brand_id == user.id)
    else:
        q = (q.join(CreatorProfile, Engagement.creator_id == CreatorProfile.id)
              .filter(CreatorProfile.user_id == user.id))
    rows = q.order_by(Engagement.id.desc()).all()
    return {"results": [engagement_out(e, db) for e in rows], "total": len(rows)}


@router.get("/{eid}")
def get_engagement(eid: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return engagement_out(load_engagement(db, eid, user), db)


@router.patch("/{eid}")
def decide(eid: int, body: DecisionIn,
           user: User = Depends(require_role("creator")),
           db: Session = Depends(get_db)):
    e = load_engagement(db, eid, user)
    if e.creator.user_id != user.id:
        raise HTTPException(403, "Only the invited creator can respond")
    if e.status != "sent":
        raise HTTPException(409, f"Cannot change a request that is already {e.status}")
    e.status = body.status
    db.commit()
    return engagement_out(e, db)


@router.get("/{eid}/messages")
def list_messages(eid: int, after_id: int = 0,
                  user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Poll with ?after_id=<last message id> to fetch only new messages."""
    e = load_engagement(db, eid, user)
    rows = (db.query(Message).filter(Message.engagement_id == e.id, Message.id > after_id)
              .order_by(Message.id).all())
    return {"results": [message_out(m) for m in rows], "status": e.status}


@router.post("/{eid}/messages", status_code=201)
def send_message(eid: int, body: MessageIn,
                 user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    e = load_engagement(db, eid, user)
    if e.status == "declined":
        raise HTTPException(409, "This request was declined, chat is closed")
    m = Message(engagement_id=e.id, sender_id=user.id, body=body.body.strip())
    db.add(m)
    db.commit()
    db.refresh(m)
    return message_out(m)


@router.post("/{eid}/confirm", status_code=201)
def confirm_deal(eid: int, body: ConfirmIn = ConfirmIn(),
                 user: User = Depends(require_role("brand")),
                 db: Session = Depends(get_db)):
    e = load_engagement(db, eid, user)
    if e.brief.brand_id != user.id:
        raise HTTPException(403, "Only the brand that sent the brief can confirm")
    if e.status != "accepted":
        raise HTTPException(409, f"Deal can only be confirmed after the creator accepts (status: {e.status})")
    b = e.brief
    deal = Deal(
        engagement_id=e.id,
        agreed_price=body.agreed_price or b.budget,
        license_type=b.license_type,          # license terms are frozen at confirmation
        usage_duration=b.usage_duration,
        territory=b.territory,
        confirmed_at=datetime.utcnow(),
    )
    e.status = "confirmed"
    b.status = "in_progress"
    db.add(deal)
    db.commit()
    db.refresh(deal)
    return deal_out(deal)


@router.post("/{eid}/deliver")
def mark_delivered(eid: int,
                   user: User = Depends(require_role("creator")),
                   db: Session = Depends(get_db)):
    e = load_engagement(db, eid, user)
    if e.creator.user_id != user.id:
        raise HTTPException(403, "Only the creator on this deal can mark it delivered")
    if e.status != "confirmed":
        raise HTTPException(409, f"Only confirmed deals can be delivered (status: {e.status})")
    e.status = "delivered"
    e.brief.status = "completed"
    db.commit()
    return engagement_out(e, db)