import re
from datetime import datetime

def is_valid_email(email: str) -> bool:
    """Validate email address format using a regular expression."""
    pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    return bool(re.match(pattern, email))

def is_valid_date(date_str: str) -> bool:
    """Validate string date matches YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
