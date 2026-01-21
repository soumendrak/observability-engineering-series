import sys
import os
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# 1. Configure for Production (JSON)
# In a real app, you might toggle this with an env var like: 
if os.getenv("ENV") == "PROD":
    logger.remove() # Remove the default human-readable handler
    logger.add(sys.stdout, serialize=True)

# 2. Define your event logic
def log_login_failure(user_id: int, error_type: str) -> None:
    # Bind the context variables so they appear as separate JSON keys
    context_logger = logger.bind(user_id=user_id, error_type=error_type)
    
    # Log the event name
    context_logger.warning("user_login_failed")

if __name__ == "__main__":
    # 3. Simulate an event
    log_login_failure(123, "invalid_password")
