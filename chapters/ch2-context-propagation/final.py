import asyncio
import random
import sys
import os
import contextvars
import functools
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# 1. Define the ContextVar
# This acts like a "Thread Local", but for Asyncio Tasks
request_id_var = contextvars.ContextVar("request_id", default=None)

# 2. Configure Logger
# We need a 'patcher' to inject the ContextVar value into every log record
def context_patcher(record):
    rid = request_id_var.get()
    if rid:
        record["extra"]["request_id"] = rid

# Configure logger with the patcher
logger.configure(patcher=context_patcher)

# In production, use JSON serialization (same pattern as Ch1)
if os.getenv("ENV") == "PROD":
    logger.remove()  # Remove the default human-readable handler
    logger.add(sys.stdout, serialize=True)

async def process_database_query():
    # Simulate DB latency
    await asyncio.sleep(random.uniform(0.1, 0.3))
    
    # No need to pass request_id! It's injected automatically by the patcher.
    logger.info("Executing DB query")

def blocking_image_processing():
    # This runs in a thread pool (blocking code)
    import time
    time.sleep(0.2)
    
    # Even inside a thread, we want context!
    # Note: For this to work, we must have copied the context when submitting the task
    rid = request_id_var.get()
    logger.info(f"Processing image in thread", thread_context_id=rid)

async def run_in_thread(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    
    # CRITICAL: Copy the current context
    ctx = contextvars.copy_context()
    
    # Wrap the function execution with ctx.run
    func_call = functools.partial(ctx.run, func, *args, **kwargs)
    
    return await loop.run_in_executor(None, func_call)

async def handle_request(request_id: str):
    # Set the ContextVar at the start of the request
    token = request_id_var.set(request_id)
    
    try:
        logger.info("Started request")
        
        # Asyncio automatically propagates context to this child coroutine
        await process_database_query()
        
        # Manually propagate context to thread pool
        await run_in_thread(blocking_image_processing)
        
        logger.info("Finished request successfully")
        
    finally:
        # Reset the context variable (good practice, though task isolation handles cleanup mostly)
        request_id_var.reset(token)

async def main():
    logger.info("Starting server simulation with ContextVars...")
    
    tasks = [handle_request(f"req-{i}") for i in range(5)]
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
