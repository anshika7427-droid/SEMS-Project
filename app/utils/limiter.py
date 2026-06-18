import sys
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# Disable rate limiting during pytest runs
is_testing = "pytest" in sys.modules or os.getenv("TESTING") == "True"
limiter = Limiter(key_func=get_remote_address, enabled=not is_testing)
