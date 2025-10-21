import os
import sys
from pathlib import Path

# Add the project root directory to Python path
ROOT_DIR = Path(__file__).parent
sys.path.append(str(ROOT_DIR))

import uvicorn
from app import app

if __name__ == "__main__":
    uvicorn.run("app:app", host="localhost", port=8000, reload=True)