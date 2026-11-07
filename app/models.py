from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_phone_verified = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    vehicle_number = Column(String(30), unique=True, index=True, nullable=False)
    contact_phone = Column(String(20), nullable=False)
    notes = Column(String(200), nullable=True)  # Instructions / emergency note
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="vehicles")
    search_logs = relationship("SearchLog", back_populates="vehicle", cascade="all, delete-orphan")


class SearchLog(Base):
    __tablename__ = "search_logs"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    searched_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    vehicle = relationship("Vehicle", back_populates="search_logs")
    searcher = relationship("User")


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), index=True, nullable=False)
    otp_code = Column(String(10), nullable=False)
    name = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    vehicle_number = Column(String(30), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
