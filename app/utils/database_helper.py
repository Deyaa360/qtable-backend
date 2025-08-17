from sqlalchemy.orm import Session
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

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
    """Log an activity to the database - DISABLED for performance"""
    # Activity logging disabled to reduce console output
    pass

def create_slug_from_name(name: str) -> str:
    """Create a URL-safe slug from a name"""
    import re
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', name.lower())
    slug = re.sub(r'\s+', '-', slug)
    slug = slug.strip('-')
    return slug[:50]  # Limit length
