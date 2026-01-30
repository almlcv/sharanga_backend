import secrets
import hashlib
from datetime import timedelta
from typing import Optional
from fastapi import HTTPException, status
import logging

from app.core.cache.cache_manager import get_dragonfly_client

logger = logging.getLogger(__name__)


class OTPService:
    """Service for OTP generation, storage, and verification using Redis"""
    
    # Configuration
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    MAX_ATTEMPTS = 3
    RATE_LIMIT_MINUTES = 15  # Prevent spam: only 1 OTP per 15 mins per user
    
    @staticmethod
    def _generate_otp() -> str:
        """Generate a 6-digit OTP"""
        return ''.join([str(secrets.randbelow(10)) for _ in range(OTPService.OTP_LENGTH)])
    
    @staticmethod
    def _hash_otp(otp: str) -> str:
        """Hash OTP for secure storage"""
        return hashlib.sha256(otp.encode()).hexdigest()
    
    @staticmethod
    def _get_cache_key(identifier: str) -> str:
        """Generate Redis key for OTP storage"""
        return f"password_reset_otp:{identifier}"
    
    @staticmethod
    def _get_rate_limit_key(identifier: str) -> str:
        """Generate Redis key for rate limiting"""
        return f"otp_rate_limit:{identifier}"
    
    @staticmethod
    async def generate_and_store_otp(identifier: str) -> str:
        """
        Generate OTP and store in Redis
        
        Args:
            identifier: Email or phone number
            
        Returns:
            Plain OTP (to be sent via email)
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        client = get_dragonfly_client()
        
        # Check rate limit
        rate_limit_key = OTPService._get_rate_limit_key(identifier)
        if client.exists(rate_limit_key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {OTPService.RATE_LIMIT_MINUTES} minutes before requesting a new OTP."
            )
        
        # Generate OTP
        otp = OTPService._generate_otp()
        hashed_otp = OTPService._hash_otp(otp)
        
        # Store in Redis
        cache_key = OTPService._get_cache_key(identifier)
        otp_data = {
            "otp_hash": hashed_otp,
            "attempts": 0,
            "verified": False
        }
        
        # Convert dict to string for Redis (simple approach)
        import json
        ttl_seconds = OTPService.OTP_EXPIRY_MINUTES * 60
        client.setex(cache_key, ttl_seconds, json.dumps(otp_data))
        
        # Set rate limit
        rate_limit_ttl = OTPService.RATE_LIMIT_MINUTES * 60
        client.setex(rate_limit_key, rate_limit_ttl, "1")
        
        logger.info(f"OTP generated for {identifier} (valid for {OTPService.OTP_EXPIRY_MINUTES} minutes)")
        return otp
    
    @staticmethod
    async def verify_otp(identifier: str, otp: str) -> bool:
        """
        Verify OTP
        
        Args:
            identifier: Email or phone number
            otp: Plain OTP entered by user
            
        Returns:
            True if OTP is valid
            
        Raises:
            HTTPException: If OTP expired, invalid, or max attempts exceeded
        """
        client = get_dragonfly_client()
        cache_key = OTPService._get_cache_key(identifier)
        
        # Get stored OTP data
        otp_data_str = client.get(cache_key)
        if not otp_data_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired or does not exist. Please request a new OTP."
            )
        
        import json
        otp_data = json.loads(otp_data_str)
        
        # Check if already verified
        if otp_data.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This OTP has already been used. Please request a new OTP."
            )
        
        # Check max attempts
        if otp_data["attempts"] >= OTPService.MAX_ATTEMPTS:
            client.delete(cache_key)  # Delete to force new OTP request
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. Please request a new OTP."
            )
        
        # Verify OTP
        hashed_input = OTPService._hash_otp(otp)
        if hashed_input != otp_data["otp_hash"]:
            # Increment attempts
            otp_data["attempts"] += 1
            
            # Get remaining TTL
            ttl = client.ttl(cache_key)
            if ttl > 0:
                client.setex(cache_key, ttl, json.dumps(otp_data))
            
            remaining_attempts = OTPService.MAX_ATTEMPTS - otp_data["attempts"]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {remaining_attempts} attempt(s) remaining."
            )
        
        # Mark as verified
        otp_data["verified"] = True
        ttl = client.ttl(cache_key)
        if ttl > 0:
            client.setex(cache_key, ttl, json.dumps(otp_data))
        
        logger.info(f"OTP verified successfully for {identifier}")
        return True
    
    @staticmethod
    async def invalidate_otp(identifier: str):
        """Delete OTP after successful password reset"""
        client = get_dragonfly_client()
        cache_key = OTPService._get_cache_key(identifier)
        client.delete(cache_key)
        logger.info(f"OTP invalidated for {identifier}")