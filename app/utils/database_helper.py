from sqlalchemy.orm import Session
from app.models import ActivityLog

def log_activity(
    db: Session,
    restaurant_id: str,
    user_id: str,
    action: str,
    entity_type: str = None,
    entity_id: str = None,
    old_data: dict = None,
    new_data: dict = None,
    metadata: dict = None
):
    """Log an activity to the database"""
    try:
        activity = ActivityLog(
            restaurant_id=restaurant_id,
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_data=old_data,
            new_data=new_data,
            log_metadata=metadata or {}
        )
        db.add(activity)
        db.commit()
    except Exception as e:
        print(f"Failed to log activity: {e}")

def create_slug_from_name(name: str) -> str:
    """Create a URL-safe slug from a name"""
    import re
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
    slug = re.sub(r'\s+', '-', slug)
    slug = slug.strip('-')
    return slug[:50]  # Limit length
