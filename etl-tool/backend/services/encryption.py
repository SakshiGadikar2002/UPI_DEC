"""
Encryption service for securely storing API credentials
Uses AES-256 encryption for sensitive data
"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from typing import Optional
import json


class EncryptionService:
    """Service for encrypting and decrypting sensitive data"""
    
    def __init__(self):
        # Get encryption key from environment variable or generate one
        encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if not encryption_key:
            # Generate a key if not provided (for development only)
            # In production, this should be set via environment variable
            print("⚠️ WARNING: ENCRYPTION_KEY not set. Using default key (NOT SECURE FOR PRODUCTION)")
            encryption_key = "default-encryption-key-change-in-production-32chars!!"
        
        # Derive a 32-byte key from the encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'etl_tool_salt_2024',  # In production, use a random salt per encryption
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
        self.cipher = Fernet(key)
    
    def encrypt(self, data: str) -> str:
        """Encrypt a string value"""
        if not data:
            return ""
        try:
            encrypted_bytes = self.cipher.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
        except Exception as e:
            print(f"❌ Encryption error: {e}")
            raise ValueError(f"Failed to encrypt data: {str(e)}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt an encrypted string value"""
        if not encrypted_data:
            return ""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            return decrypted_bytes.decode()
        except Exception as e:
            print(f"❌ Decryption error: {e}")
            raise ValueError(f"Failed to decrypt data: {str(e)}")
    
    def encrypt_dict(self, data: dict) -> str:
        """Encrypt a dictionary by converting to JSON first"""
        if not data:
            return ""
        json_str = json.dumps(data)
        return self.encrypt(json_str)
    
    def decrypt_dict(self, encrypted_data: str) -> dict:
        """Decrypt and parse JSON back to dictionary"""
        if not encrypted_data or encrypted_data.strip() == "":
            return {}
        try:
            json_str = self.decrypt(encrypted_data)
            return json.loads(json_str)
        except Exception as e:
            # If decryption fails, try to parse as plain JSON (for backward compatibility)
            try:
                return json.loads(encrypted_data)
            except:
                raise ValueError(f"Failed to decrypt or parse data: {str(e)}")
    
    def encrypt_credentials(self, credentials: dict) -> str:
        """Encrypt API credentials dictionary"""
        return self.encrypt_dict(credentials)
    
    def decrypt_credentials(self, encrypted_credentials: str) -> dict:
        """Decrypt API credentials dictionary"""
        if not encrypted_credentials or encrypted_credentials.strip() == "":
            return {}
        return self.decrypt_dict(encrypted_credentials)


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service

