from passlib.context import CryptContext
from database import SessionLocal, engine, Base
from models import (User, CreatorProfile, Tool, Skill, CreatorTool, CreatorSkill,
                    PortfolioItem, PortfolioItemTool)

Base.metadata.create_all(bind=engine)
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
db = SessionLocal()

# name, specialization, rate_min, rate_max, bio, tools, verified_tools, skills, workflow_verified, works
# work = (title, content_type, is_ai, tools, workflow, past_work_verified)
DATA = [
 ("Aarav Nair","AI Filmmaking",30000,60000,"Short-form ad films with consistent characters.",
  ["Sora","Runway","Kling"],["Sora","Runway"],["Storytelling","Cinematic","Color grading"],True,
  [("Monsoon Chai 30s ad","video",True,["Sora","Runway"],"Script, Sora shots, Runway Act-One, DaVinci grade",True),
   ("Metro Nights teaser","video",True,["Kling"],"Storyboard, Kling image-to-video, CapCut edit",True)]),
 ("Meera Iyer","AI Animation",20000,40000,"Playful 2D and 3D mascots brought to life.",
  ["Midjourney","Pika","After Effects"],["Midjourney"],["2D animation","Character design","Motion graphics"],False,
  [("Mascot loop for SnackCo","animation",True,["Midjourney","Pika"],"MJ character sheet, Pika animate, AE polish",True),
   ("Festive greeting","animation",True,["Pika"],"Keyframes, Pika interpolation",False)]),
 ("Rohan Das","Brand Graphics",8000,20000,"Logo explorations and packaging mockups at speed.",
  ["Midjourney","Firefly","Figma"],["Midjourney","Figma"],["Logo design","Packaging","Typography"],True,
  [("Tea brand logo set","logo",True,["Midjourney","Figma"],"Prompt grid, vectorise, Figma refine",False),
   ("Hand-drawn festival poster","graphic",False,["Procreate"],"Human-made, no AI",True)]),
 ("Sana Khan","Product Promotion",15000,35000,"Vertical product reels for D2C brands.",
  ["Runway","Veo","Photoshop"],[],["Product shots","Social reels","UGC style"],True,
  [("Sneaker drop reel","social_reel",True,["Veo","Runway"],"Product photo, Veo motion, Runway relight",True),
   ("Skincare unboxing","social_reel",False,["Photoshop"],"Human-shot, AI captions",False)]),
 ("Vikram Rao","Web & App Visuals",12000,25000,"3D hero visuals and app store assets.",
  ["Midjourney","Spline","Figma"],["Spline"],["UI illustration","3D icons","Landing pages"],False,
  [("Fintech app hero","web",True,["Midjourney","Spline"],"MJ concepts, Spline 3D, export",False),
   ("Travel app store assets","app",True,["Midjourney","Figma"],"MJ scenes, Figma layout",False)]),
 ("Isha Menon","AI Filmmaking",40000,80000,"Surreal music videos and dreamlike brand films.",
  ["Kling","Sora","Suno"],["Kling","Sora"],["Music video","Surreal","VFX"],True,
  [("Indie single video","video",True,["Kling","Suno"],"Suno track, Kling shots, beat-synced edit",True)]),
 ("Karthik Reddy","AI Animation",18000,35000,"Explainer animations for startups and edtech.",
  ["Runway","Pika","Figma"],["Runway"],["Explainer","Motion graphics","Storyboarding"],False,
  [("Edtech explainer 60s","animation",True,["Runway","Pika"],"Storyboard in Figma, Pika scenes, Runway cleanup",True)]),
 ("Priya Sharma","Brand Graphics",6000,15000,"Social media graphics and brand kits.",
  ["Firefly","Midjourney","Canva"],["Firefly"],["Social graphics","Brand kits","Illustration"],False,
  [("Festive sale carousel","graphic",True,["Firefly","Canva"],"Firefly backgrounds, Canva layout",False),
   ("Cafe brand kit","logo",True,["Midjourney"],"MJ marks, manual refinement",True)]),
 ("Dev Malhotra","Product Promotion",25000,50000,"Cinematic product films for electronics and fashion.",
  ["Sora","Veo","DaVinci Resolve"],["Veo"],["Product shots","Cinematic","Color grading"],True,
  [("Earbuds launch film","video",True,["Veo","Sora"],"Veo hero shots, Sora b-roll, DaVinci grade",True)]),
 ("Ananya Pillai","AI Filmmaking",22000,45000,"Narrative shorts and festival-style brand stories.",
  ["Runway","Kling","ElevenLabs"],["Runway"],["Storytelling","Voiceover","Cinematic"],False,
  [("Heritage saree story","video",True,["Runway","ElevenLabs"],"Script, Runway shots, ElevenLabs voice",False)]),
 ("Nikhil Verma","Web & App Visuals",10000,22000,"Landing page visuals and product mockups.",
  ["Midjourney","Figma","Spline"],[],["Landing pages","Mockups","3D icons"],False,
  [("SaaS dashboard hero","web",True,["Midjourney","Figma"],"MJ abstract art, Figma composition",False)]),
 ("Zoya Ali","Product Promotion",14000,30000,"Fashion and beauty reels with AI-generated models.",
  ["Kling","Runway","Photoshop"],["Kling"],["Social reels","Fashion","UGC style"],True,
  [("Lipstick launch reel","social_reel",True,["Kling","Photoshop"],"Model refs, Kling motion, PS retouch",True)]),
]

def get_or_create(model, name):
    obj = db.query(model).filter(model.name == name).first()
    if not obj:
        obj = model(name=name)
        db.add(obj)
        db.flush()
    return obj

for i, (name, spec, rmin, rmax, bio, tools, vtools, skills, wfv, works) in enumerate(DATA, 1):
    email = f"seed{i}@creators.test"
    if db.query(User).filter(User.email == email).first():
        continue
    u = User(email=email, username=f"creator_{i}", phone=f"+9190000000{i:02d}",
             password_hash=pwd.hash("secret123"), role="creator", is_verified=True)
    db.add(u)
    db.flush()
    p = CreatorProfile(user_id=u.id, display_name=name, bio=bio, specialization=spec,
                       rate_min=rmin, rate_max=rmax, workflow_verified=wfv)
    db.add(p)
    db.flush()
    for t in tools:
        p.tools.append(CreatorTool(tool_id=get_or_create(Tool, t).id, is_verified=t in vtools))
    for s in skills:
        p.skills.append(CreatorSkill(skill_id=get_or_create(Skill, s).id))
    for title, ctype, ai, wtools, wf, pv in works:
        item = PortfolioItem(creator_id=p.id, title=title, content_type=ctype,
                             is_ai_generated=ai, workflow_notes=wf, past_work_verified=pv,
                             media_url="https://example.com/" + title.lower().replace(" ", "-"))
        for t in wtools:
            item.tools.append(PortfolioItemTool(tool_id=get_or_create(Tool, t).id))
        p.portfolio.append(item)
    db.commit()

print("Seeded. Creators in DB:", db.query(CreatorProfile).count())
db.close()