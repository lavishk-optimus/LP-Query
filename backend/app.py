from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api import fund_upload_router
from api import fund_data_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create FastAPI app
app = FastAPI(
    title="LP Query Backend",
    description="API for processing fund documents and managing fund data",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(fund_upload_router)
app.include_router(fund_data_router)

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "LP Query Backend API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "LP Query Backend"}