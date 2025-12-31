import os
from dotenv import load_dotenv
from datetime import datetime, timezone

# Load environment variables from .env file if it exists
load_dotenv()

class Settings:
    """Application settings"""
    
    # Database settings
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./heart_rate.db")
    
    # Server settings
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
    
    # CORS settings
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # Application settings
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    
    # WebSocket settings
    WS_MAX_CONNECTIONS = int(os.getenv("WS_MAX_CONNECTIONS", "100"))
    
    # Timezone settings
    TIMEZONE = timezone.utc

# Create settings instance
settings = Settings()
