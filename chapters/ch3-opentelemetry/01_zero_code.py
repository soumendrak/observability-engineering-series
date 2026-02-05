import asyncio
import os
import sys
from fastapi import FastAPI
import uvicorn
import httpx
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

# Match the structured logging pattern from Chapter 1 & 2
if os.getenv("ENV") == "PROD":
    logger.remove()
    logger.add(sys.stdout, serialize=True)

app = FastAPI()

@app.get("/")
async def root():
    logger.info("Received request in Zero-Code app")
    
    # Simulate an external API call
    async with httpx.AsyncClient() as client:
        await client.get("https://www.soumendrak.com")
        
    logger.info("External call completed")
    return {"message": "Zero-code instrumentation works!"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

