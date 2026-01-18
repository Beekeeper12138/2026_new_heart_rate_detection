from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import numpy as np
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
                frame_with_boxes, rois, face_locations, processing_resolution = face_service.process_frame(frame)
                
                # Calculate heart rate for each face
                heart_rates = rppg_service.process_multiple_rois(rois)
                
                # Get processed signal for visualization
                processed_signal = rppg_service.get_processed_signal()
                
                # If we don't have enough filtered signal, use raw signal buffer
                if len(processed_signal) < 10:
                    processed_signal = np.array(rppg_service.signal_buffer)
                
                # Convert face locations to Python integers to avoid JSON serialization error
                # Ensure all coordinates are Python ints, not NumPy types
                python_face_locations = []
                for loc in face_locations:
                    if loc and len(loc) == 4:
                        # Convert each coordinate to Python int
                        python_loc = [int(coord) for coord in loc]
                        python_face_locations.append(python_loc)
                
                # Prepare response data - send face coordinates, heart rate data, and processing resolution
                response = {
                    "status": "success",
                    "heart_rates": [round(float(hr), 1) for hr in heart_rates],  # Ensure Python float
                    "num_faces": int(len(rois)),  # Ensure Python int
                    "signal": processed_signal.tolist()[-50:],  # Send only last 50 points for visualization
                    "face_coordinates": python_face_locations,  # Send face coordinates as Python ints
                    "processing_resolution": {
                        "width": int(processing_resolution[0]),  # Ensure Python int
                        "height": int(processing_resolution[1])  # Ensure Python int
                    }
                }
                
                # Debug: Check response structure
                print(f"Response keys: {list(response.keys())}")
                print(f"Number of faces detected: {len(rois)}")
                print(f"Face coordinates: {face_locations}")
                
                # Send response back to client
                await manager.send_json(response, websocket)
                print("Response sent to client")
                
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
