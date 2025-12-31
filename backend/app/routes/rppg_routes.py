from fastapi import APIRouter, Depends, Query, Form
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from config import settings

from app.models.heart_rate import HeartRate
from app.utils.database import get_db

router = APIRouter()

@router.get("/calculate")
async def calculate_heart_rate():
    """Calculate heart rate using rPPG"""
    return {"message": "rPPG heart rate calculation endpoint"}

@router.post("/save")
async def save_heart_rate(
    heart_rate: float = Form(...),
    user_id: str = Form(None),
    device_type: str = Form(None),
    device_id: str = Form(None),
    confidence: float = Form(None),
    db: Session = Depends(get_db)
):
    """Save heart rate data to database"""
    db_heart_rate = HeartRate(
        heart_rate=heart_rate,
        timestamp=datetime.now(),
        user_id=user_id,
        device_type=device_type,
        device_id=device_id,
        confidence=confidence
    )
    db.add(db_heart_rate)
    db.commit()
    db.refresh(db_heart_rate)
    
    return {
        "status": "success",
        "data": {
            "id": db_heart_rate.id,
            "heart_rate": db_heart_rate.heart_rate,
            "timestamp": db_heart_rate.timestamp,
            "user_id": db_heart_rate.user_id
        }
    }

@router.get("/history")
async def get_heart_rate_history(
    user_id: str = Query(None, description="Filter by user ID"),
    device_type: str = Query(None, description="Filter by device type"),
    start_time: datetime = Query(None, description="Start time for history"),
    end_time: datetime = Query(None, description="End time for history"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """Get historical heart rate data"""
    query = db.query(HeartRate)
    
    # Apply filters
    if user_id:
        query = query.filter(HeartRate.user_id == user_id)
    if device_type:
        query = query.filter(HeartRate.device_type == device_type)
    if start_time:
        query = query.filter(HeartRate.timestamp >= start_time)
    if end_time:
        query = query.filter(HeartRate.timestamp <= end_time)
    
    # If no time range specified, default to last 24 hours
    if not start_time and not end_time:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        query = query.filter(HeartRate.timestamp >= start_time, HeartRate.timestamp <= end_time)
    
    # Execute query with limit and order by timestamp desc
    heart_rates = query.order_by(HeartRate.timestamp.desc()).limit(limit).all()
    
    # Format response
    result = [
        {
            "id": hr.id,
            "heart_rate": hr.heart_rate,
            "timestamp": hr.timestamp,
            "user_id": hr.user_id,
            "device_type": hr.device_type,
            "device_id": hr.device_id,
            "confidence": hr.confidence
        }
        for hr in heart_rates
    ]
    
    return {
        "status": "success",
        "data": result,
        "count": len(result)
    }

@router.get("/stats")
async def get_heart_rate_stats(
    user_id: str = Query(None, description="Filter by user ID"),
    start_time: datetime = Query(None, description="Start time for stats"),
    end_time: datetime = Query(None, description="End time for stats"),
    db: Session = Depends(get_db)
):
    """Get heart rate statistics"""
    query = db.query(HeartRate)
    
    # Apply filters
    if user_id:
        query = query.filter(HeartRate.user_id == user_id)
    if start_time:
        query = query.filter(HeartRate.timestamp >= start_time)
    if end_time:
        query = query.filter(HeartRate.timestamp <= end_time)
    
    # If no time range specified, default to last 24 hours
    if not start_time and not end_time:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        query = query.filter(HeartRate.timestamp >= start_time, HeartRate.timestamp <= end_time)
    
    # Get all heart rates in the time range
    heart_rates = query.all()
    
    if not heart_rates:
        return {
            "status": "success",
            "data": {
                "average": 0,
                "min": 0,
                "max": 0,
                "count": 0
            }
        }
    
    # Calculate statistics
    heart_rate_values = [hr.heart_rate for hr in heart_rates]
    average_hr = sum(heart_rate_values) / len(heart_rate_values)
    min_hr = min(heart_rate_values)
    max_hr = max(heart_rate_values)
    
    return {
        "status": "success",
        "data": {
            "average": round(average_hr, 1),
            "min": round(min_hr, 1),
            "max": round(max_hr, 1),
            "count": len(heart_rates)
        }
    }
