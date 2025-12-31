from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.websocket import ConnectionManager
from app.services.face_recognition import FaceRecognitionService
from app.services.rppg import RPPGService

router = APIRouter()
manager = ConnectionManager()

# Create service instances for each connection
face_services = {}
rppg_services = {}

@router.websocket("/heartrate")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time heart rate monitoring"""
    await manager.connect(websocket)
    
    # Create service instances for this connection
    face_service = FaceRecognitionService()
    rppg_service = RPPGService()
    
    # Store services in dictionaries
    client_id = id(websocket)
    face_services[client_id] = face_service
    rppg_services[client_id] = rppg_service
    
    try:
        while True:
            data = await websocket.receive_text()
            
            try:
                # Decode the image data
                frame = face_service.decode_image(data)
                
                # Detect faces and extract ROIs
                frame_with_boxes, rois = face_service.process_frame(frame)
                
                # Calculate heart rate for each face
                heart_rates = rppg_service.process_multiple_rois(rois)
                
                # Get processed signal for visualization (optional)
                processed_signal = rppg_service.get_processed_signal().tolist()
                
                # Prepare response data
                response = {
                    "status": "success",
                    "heart_rates": [round(hr, 1) for hr in heart_rates],
                    "num_faces": len(rois),
                    "signal": processed_signal[:50]  # Send only last 50 points for visualization
                }
                
                # Send response back to client
                await manager.send_json(response, websocket)
                
            except Exception as e:
                # Send error response
                await manager.send_json({
                    "status": "error",
                    "message": str(e)
                }, websocket)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        # Clean up service instances
        if client_id in face_services:
            del face_services[client_id]
        if client_id in rppg_services:
            del rppg_services[client_id]
    except Exception as e:
        manager.disconnect(websocket)
        # Clean up service instances
        if client_id in face_services:
            del face_services[client_id]
        if client_id in rppg_services:
            del rppg_services[client_id]
