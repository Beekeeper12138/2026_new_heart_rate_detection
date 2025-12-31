from fastapi import APIRouter

router = APIRouter()

@router.get("/detect")
async def detect_face():
    """Detect face from image"""
    return {"message": "Face detection endpoint"}

@router.get("/recognize")
async def recognize_face():
    """Recognize face from image"""
    return {"message": "Face recognition endpoint"}
