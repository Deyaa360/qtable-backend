from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Database
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./qtable.db")
    
    # JWT
    secret_key: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    algorithm: str = os.getenv("ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Redis
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # WebSocket Configuration
    ws_heartbeat_interval: int = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    ws_connection_timeout: int = int(os.getenv("WS_CONNECTION_TIMEOUT", "300"))
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS
    cors_origins: list = ["*"]  # In production, specify exact origins
    
    class Config:
        env_file = ".env"

settings = Settings()
