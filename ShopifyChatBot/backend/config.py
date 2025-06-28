import os
from pathlib import Path
from dotenv import load_dotenv

# Get the absolute path to the backend directory
BACKEND_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
env_path = BACKEND_DIR / '.env'
load_dotenv(dotenv_path=env_path)

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please create a .env file in the backend directory with your OpenAI API key.") 