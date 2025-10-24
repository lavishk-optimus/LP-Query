from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from api.routes import router
import uvicorn
from services.telemetry_client import telemetry_client
from api import fund_upload_router
from api import fund_data_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress Azure SDK verbose logging
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
logging.getLogger('azure.core').setLevel(logging.WARNING)
logging.getLogger('azure').setLevel(logging.WARNING)

# Create FastAPI app
app = FastAPI(
    title="LP Query Backend",
    description="API for processing fund documents and managing fund data",
    version="1.0.0"
)
telemetry_client.log_info('FastAPI instance created...')
app.include_router(router)

telemetry_client.log_info('🔗 Routes registered successfully...')

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


if __name__ == '__main__':
    telemetry_client.log_info(' Starting Uvicorn...')
    uvicorn.run(app, host='0.0.0.0', port=8080)