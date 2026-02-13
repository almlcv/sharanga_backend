import secrets
import hashlib
from fastapi import HTTPException, status
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class OTPService:
    """Service for OTP generation, storage, and verification using in-memory storage"""
    
    # Configuration
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    MAX_ATTEMPTS = 3
    RATE_LIMIT_MINUTES = 15  # Prevent spam: only 1 OTP per 15 mins per user
    
    # In-memory storage (simple approach - use database for production)
    _otp_store: Dict[str, Dict] = {}
    _rate_limit_store: Dict[str, datetime] = {}
    
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
        """Generate key for OTP storage"""
        return f"password_reset_otp:{identifier}"
    
    @staticmethod
    def _get_rate_limit_key(identifier: str) -> str:
        """Generate key for rate limiting"""
        return f"otp_rate_limit:{identifier}"
    
    @staticmethod
    def _cleanup_expired_entries():
        """Clean up expired OTP and rate limit entries from memory"""
        current_time = datetime.now()
        
        # Clean up expired OTPs
        expired_otps = [
            key for key, data in OTPService._otp_store.items()
            if current_time > data["expires_at"]
        ]
        for key in expired_otps:
            del OTPService._otp_store[key]
        
        # Clean up expired rate limits
        expired_rate_limits = [
            key for key, expiry_time in OTPService._rate_limit_store.items()
            if current_time > expiry_time
        ]
        for key in expired_rate_limits:
            del OTPService._rate_limit_store[key]
        
        if expired_otps or expired_rate_limits:
            logger.debug(f"Cleaned up {len(expired_otps)} expired OTPs and {len(expired_rate_limits)} expired rate limits")
    
    @staticmethod
    async def generate_and_store_otp(identifier: str) -> str:
        """
        Generate OTP and store in memory
        
        Args:
            identifier: Email or phone number
            
        Returns:
            Plain OTP (to be sent via email)
            
        Raises:
            HTTPException: If rate limit exceeded
        """
        # Clean up expired entries first
        OTPService._cleanup_expired_entries()
        
        # Check rate limit
        rate_limit_key = OTPService._get_rate_limit_key(identifier)
        if rate_limit_key in OTPService._rate_limit_store:
            if datetime.now() < OTPService._rate_limit_store[rate_limit_key]:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {OTPService.RATE_LIMIT_MINUTES} minutes before requesting a new OTP."
                )
        
        # Generate OTP
        otp = OTPService._generate_otp()
        hashed_otp = OTPService._hash_otp(otp)
        
        # Store in memory
        cache_key = OTPService._get_cache_key(identifier)
        otp_data = {
            "otp_hash": hashed_otp,
            "attempts": 0,
            "verified": False,
            "expires_at": datetime.now() + timedelta(minutes=OTPService.OTP_EXPIRY_MINUTES)
        }
        
        OTPService._otp_store[cache_key] = otp_data
        
        # Set rate limit
        OTPService._rate_limit_store[rate_limit_key] = datetime.now() + timedelta(minutes=OTPService.RATE_LIMIT_MINUTES)
        
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
        # Clean up expired entries first
        OTPService._cleanup_expired_entries()
        
        cache_key = OTPService._get_cache_key(identifier)
        
        # Get stored OTP data
        if cache_key not in OTPService._otp_store:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired or does not exist. Please request a new OTP."
            )
        
        otp_data = OTPService._otp_store[cache_key]
        
        # Check if expired
        if datetime.now() > otp_data["expires_at"]:
            del OTPService._otp_store[cache_key]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new OTP."
            )
        
        # Check if already verified
        if otp_data.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This OTP has already been used. Please request a new OTP."
            )
        
        # Check max attempts
        if otp_data["attempts"] >= OTPService.MAX_ATTEMPTS:
            del OTPService._otp_store[cache_key]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. Please request a new OTP."
            )
        
        # Verify OTP
        hashed_input = OTPService._hash_otp(otp)
        if hashed_input != otp_data["otp_hash"]:
            # Increment attempts
            otp_data["attempts"] += 1
            
            remaining_attempts = OTPService.MAX_ATTEMPTS - otp_data["attempts"]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {remaining_attempts} attempt(s) remaining."
            )
        
        # Mark as verified
        otp_data["verified"] = True
        
        logger.info(f"OTP verified successfully for {identifier}")
        return True
    
    @staticmethod
    async def invalidate_otp(identifier: str):
        """Delete OTP after successful password reset"""
        cache_key = OTPService._get_cache_key(identifier)
        if cache_key in OTPService._otp_store:
            del OTPService._otp_store[cache_key]
        logger.info(f"OTP invalidated for {identifier}")
