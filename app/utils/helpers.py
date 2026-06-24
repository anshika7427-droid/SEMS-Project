from datetime import date, datetime
from typing import Union
from fastapi import Query

def pagination_params(skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    return {"skip": skip, "limit": limit}


def parse_date(value: Union[str, date, datetime]) -> date:
    """Parse a date from a string in any known app format, or pass through a date/datetime."""
    if isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    if not isinstance(value, str):
        raise ValueError(f"Cannot parse date from type {type(value)}")
    value = value.strip()
    # Strip time component
    value = value.split()[0].split('T')[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date from string: {value!r}")

def format_user_summary(user_name: str, email: str) -> str:
    """Format user information for logs or summary displays."""
    return f"{user_name} ({email})"

def calculate_completion_rate(completed: int, total: int) -> float:
    """Calculate the completion percentage rate."""
    if total <= 0:
        return 0.0
    return round((completed / total) * 100, 2)
