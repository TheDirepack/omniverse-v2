import uuid


def is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
    except (ValueError, AttributeError):
        return False
    else:
        return True


def get_active_world_id(cookie_value: str | None) -> str | None:
    if cookie_value and is_valid_uuid(cookie_value):
        return cookie_value
    return None
