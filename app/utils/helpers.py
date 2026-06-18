def format_user_summary(user_name: str, email: str) -> str:
    """Format user information for logs or summary displays."""
    return f"{user_name} ({email})"

def calculate_completion_rate(completed: int, total: int) -> float:
    """Calculate the completion percentage rate."""
    if total <= 0:
        return 0.0
    return round((completed / total) * 100, 2)
