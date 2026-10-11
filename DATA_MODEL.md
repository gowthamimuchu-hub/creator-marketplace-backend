# Data model note

## Creator profile and AI portfolio
**users:** id, email, username, phone, password_hash, role (brand | creator), is_verified.

**creator_profiles:** display_name, bio, specialization, rate_min, rate_max,
availability (available | busy | unavailable), workflow_verified (badge).

**tools / skills:** shared catalogs (e.g. Sora, Runway, Midjourney; Storytelling, Logo design).
Linked to creators through **creator_tools** (with `is_verified`, the verified-tool badge)
and **creator_skills**.

**portfolio_items:** title, media_url, thumbnail_url,
content_type (video | animation | graphic | logo | web | app | social_reel),
is_ai_generated, workflow_notes, past_work_verified (badge).
Tools used per piece are stored in **portfolio_item_tools**.

## Brief
**briefs:** title, description (campaign requirements),
content_type, style (cinematic | playful | minimal | retro | surreal_3d | corporate),
aspect_ratio (9:16 | 16:9 | 1:1 | 4:5), platforms, budget, deadline, revisions, status.

**Commercial-use fields:**
- license_type: full_commercial | social_only | digital_ads | broadcast | internal_only
- usage_duration: 6_months | 1_year | 3_years | perpetual
- territory: india | apac | global

## Engagement
**engagements:** brief_id, creator_id, status: sent, accepted or declined, then confirmed, then delivered.
**messages:** engagement_id, sender_id, body, created_at.
**deals:** engagement_id, agreed_price, license_type, usage_duration, territory, confirmed_at.
Commercial-use terms are copied from the brief when the deal is confirmed,
so the agreed license cannot change later.

## Verification signals (bonus)
- Tools verified: `creator_tools.is_verified`
- Workflow verified: `creator_profiles.workflow_verified`
- Past work verified: `portfolio_items.past_work_verified`
The API returns these as a `badges` object on every creator.