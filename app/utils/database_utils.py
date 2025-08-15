from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, Dict, Any

def set_restaurant_context(db: Session, restaurant_id: str):
    """Set the restaurant context for Row Level Security"""
    db.execute(text(f"SET app.current_restaurant_id = :restaurant_id"), {"restaurant_id": restaurant_id})

def log_activity(
    db: Session,
    restaurant_id: str,
    user_id: Optional[str],
    action: str,
    entity_type: str,
    entity_id: str,
    old_data: Optional[Dict[str, Any]] = None,
    new_data: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Log an activity for auditing purposes"""
    from app.models import ActivityLog
    
    log_entry = ActivityLog(
        restaurant_id=restaurant_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
        metadata=metadata or {}
    )
    
    db.add(log_entry)
    db.commit()

def create_slug_from_name(name: str, existing_slugs: list = None) -> str:
    """Create a unique URL-safe slug from a name"""
    import re
    import uuid
    
    # Clean the name
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
    slug = re.sub(r'\s+', '-', slug)
    slug = slug.strip('-')
    slug = slug[:50]  # Limit length
    
    # If no existing slugs provided, return as is
    if not existing_slugs:
        return slug or str(uuid.uuid4())[:8]
    
    # Check for uniqueness
    original_slug = slug
    counter = 1
    while slug in existing_slugs:
        slug = f"{original_slug}-{counter}"
        counter += 1
    
    return slug or str(uuid.uuid4())[:8]
