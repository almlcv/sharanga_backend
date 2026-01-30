from pydantic import AnyUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    """
    Application settings class.
    Reads variables from .env file automatically.
    """

    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")

    # API Config
    PROJECT_NAME: str
    API_V1_STR: str
    
    # MongoDB Config
    MONGODB_URL: AnyUrl
    DATABASE_NAME: str
    
    # Security Config
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Environment
    ENVIRONMENT: str = "development"

    # Redis
    REDIS_HOST: str
    REDIS_PORT: str

    # Email Configuration
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    MAIL_FROM_NAME: str

    # Pydantic V2 Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,  
        extra="ignore"  
    )
# It creates the 'settings' object that main.py uses.
config = Settings()
