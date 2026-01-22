import asyncio
import random
import sys
from loguru import logger

# 1. Configure Logger (same as Ch1 final.py)
logger.remove()
logger.add(sys.stdout, serialize=True)

# THE PROBLEM: Global state
# In Chapter 1, we learned to pass context (user_id) explicitly.
# But what if we try to use a global variable to avoid passing arguments everywhere?
current_request_id = None

async def process_database_query():
    # Simulate DB latency
    await asyncio.sleep(random.uniform(0.1, 0.3))
    
    # Log with the global context
    # PROBLEM: 'current_request_id' might have been changed by another task!
    logger.info("Executing DB query", request_id=current_request_id)

async def handle_request(request_id: str):
    global current_request_id
    
    # Set the global request ID
    current_request_id = request_id
    logger.info("Started request", request_id=current_request_id)
    
    # Retrieve some data
    await process_database_query()
    
    # Check if our ID is still correct
    if current_request_id == request_id:
        logger.info("Finished request successfully", request_id=current_request_id)
    else:
        # This is the disaster case: we are logging with SOMEONE ELSE'S ID!
        logger.error("Finished request - CONTEXT MISMATCH", 
                     expected_id=request_id, 
                     actual_global_id=current_request_id)

async def main():
    logger.info("Starting server simulation...")
    
    # Simulate 5 concurrent requests
    # Since they run on the same event loop, they share the single 'current_request_id' variable
    tasks = [handle_request(f"req-{i}") for i in range(5)]
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
