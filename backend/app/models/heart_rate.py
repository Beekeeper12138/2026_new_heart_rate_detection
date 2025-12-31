from sqlalchemy import Column, Integer, Float, String, DateTime
from sqlalchemy.sql import func
from datetime import datetime, timezone
from app.utils.database import Base

class HeartRate(Base):
    """Heart rate data model"""
    __tablename__ = "heart_rates"
    
    id = Column(Integer, primary_key=True, index=True)
    heart_rate = Column(Float, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), index=True)
    user_id = Column(String(50), nullable=True, index=True)  # Optional user identifier
    device_type = Column(String(20), nullable=True)  # e.g., "desktop", "mobile"
    device_id = Column(String(50), nullable=True)  # Unique device identifier
    confidence = Column(Float, nullable=True)  # Confidence level of the reading
    
    def __repr__(self):
        return f"<HeartRate(id={self.id}, heart_rate={self.heart_rate}, timestamp={self.timestamp})>"

class User(Base):
    """User data model"""
    __tablename__ = "users"
    
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=True)
    email = Column(String(100), nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email})>"
