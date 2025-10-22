from fastapi import FastAPI
from api.routes import router
import uvicorn
from services.telemetry_client import telemetry_client


app = FastAPI(title='GameDayIQ', version='1.0')

telemetry_client.log_info('FastAPI instance created...')
app.include_router(router)
telemetry_client.log_info('🔗 Routes registered successfully...')

if __name__ == '__main__':
    telemetry_client.log_info(' Starting Uvicorn...')
    uvicorn.run(app, host='0.0.0.0', port=8080)
