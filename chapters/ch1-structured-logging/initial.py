import logging
import sys

# Configure logging to output to stdout with a format similar to the blog post example
# Example output: 2026-01-21 10:00:01 WARNING:root:User 123 failed to login with error: invalid_password
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s:%(name)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout
)

def log_login_failure(user_id: int, error_type: str) -> None:
    # This represents the "Problem": Embedding data into a string
    logging.warning(f"User {user_id} failed to login with error: {error_type}")

if __name__ == "__main__":
    # Simulate an event
    log_login_failure(123, "invalid_password")
