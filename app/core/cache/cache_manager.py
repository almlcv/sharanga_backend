import redis
from app.core.setting import config
import logging
from fastapi.exceptions import HTTPException



#  INITIALIZE CONNECTION

# Set up logger
logger = logging.getLogger(__name__)

# We use a simple global variable. In larger apps, use a Singleton class.
_dragonfly_client = None

def get_dragonfly_client():
    """
    Returns the Dragonfly (Redis) client instance.
    Initializes it only once.
    """
    global _dragonfly_client
    
    if _dragonfly_client is None:
        try:
            _dragonfly_client = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT, 
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5
            )
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Dragonfly: {e}")
            raise HTTPException(500, "Cache unavailable")
    return _dragonfly_client
