import cv2
import numpy as np

class FaceRecognitionService:
    def __init__(self):
        self.face_locations = []
        self.face_encodings = []
        self.face_names = []
        self.process_this_frame = True
        
        # Load Haar cascade for face detection (built-in OpenCV)
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    def detect_faces(self, frame):
        """
        Detect faces in a frame and return their locations
        
        Args:
            frame: numpy array representing the image frame
            
        Returns:
            list: List of face locations in format (top, right, bottom, left)
        """
        # Convert frame to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. First pass: Strong glare reduction using adaptive thresholding
        # Create a binary mask for bright regions (likely glare)
        _, glare_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        
        # 2. Apply morphology to remove small bright spots and fill holes
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        glare_mask = cv2.morphologyEx(glare_mask, cv2.MORPH_CLOSE, kernel)
        glare_mask = cv2.morphologyEx(glare_mask, cv2.MORPH_OPEN, kernel)
        
        # 3. Inpaint the glare regions to reconstruct facial features
        inpainted_gray = cv2.inpaint(gray, glare_mask, 3, cv2.INPAINT_TELEA)
        
        # 4. Apply CLAHE with more aggressive parameters for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
        enhanced_gray = clahe.apply(inpainted_gray)
        
        # 5. Multi-scale blur for different levels of noise reduction
        blurred_gray = cv2.GaussianBlur(enhanced_gray, (5, 5), 0)
        
        # 6. Edge enhancement to preserve facial features lost during blur
        edge_enhanced = cv2.addWeighted(blurred_gray, 1.5, cv2.GaussianBlur(blurred_gray, (0,0), 3), -0.5, 0)
        
        # 7. Multi-pass detection approach - combine results from different parameter sets
        # First pass: Very sensitive detection
        faces1 = self.face_cascade.detectMultiScale(
            edge_enhanced,
            scaleFactor=1.02,  # Extremely sensitive scale factor
            minNeighbors=1,     # Very low threshold
            minSize=(10, 10),   # Detect very small faces
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # Second pass: Slightly more conservative to filter false positives
        faces2 = self.face_cascade.detectMultiScale(
            edge_enhanced,
            scaleFactor=1.05,  # Moderate scale factor
            minNeighbors=2,     # Slightly higher threshold
            minSize=(20, 20),   # Slightly larger minimum size
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # Combine results from both passes, removing duplicates
        faces = []
        all_faces = list(faces1) + list(faces2)
        
        # Remove duplicate faces (using simple distance check)
        for (x, y, w, h) in all_faces:
            duplicate = False
            for (x2, y2, w2, h2) in faces:
                # Check if centers are close (within 20% of face width)
                center_dist = ((x + w/2 - (x2 + w2/2)) ** 2 + (y + h/2 - (y2 + h2/2)) ** 2) ** 0.5
                if center_dist < min(w, h) * 0.2:
                    duplicate = True
                    break
            if not duplicate:
                faces.append((x, y, w, h))
        
        # Convert from (x, y, w, h) to (top, right, bottom, left) format
        face_locations = []
        for (x, y, w, h) in faces:
            top = y
            right = x + w
            bottom = y + h
            left = x
            face_locations.append((top, right, bottom, left))
        
        return face_locations
    
    def extract_roi(self, frame, face_location):
        """
        Extract Region of Interest (ROI) from face for rPPG analysis
        Focus on forehead and cheeks area which are good for blood flow detection
        
        Args:
            frame: numpy array representing the image frame
            face_location: Tuple of (top, right, bottom, left) representing face coordinates
            
        Returns:
            numpy array: ROI image
        """
        top, right, bottom, left = face_location
        
        # Calculate ROI coordinates
        # Expand the forehead area and include cheeks
        forehead_top = max(0, top - int((bottom - top) * 0.1))
        forehead_bottom = top + int((bottom - top) * 0.3)
        forehead_left = left + int((right - left) * 0.2)
        forehead_right = right - int((right - left) * 0.2)
        
        # Ensure ROI is within frame bounds
        h, w = frame.shape[:2]
        forehead_top = max(0, forehead_top)
        forehead_bottom = min(h, forehead_bottom)
        forehead_left = max(0, forehead_left)
        forehead_right = min(w, forehead_right)
        
        # Extract ROI
        roi = frame[forehead_top:forehead_bottom, forehead_left:forehead_right]
        
        return roi
    
    def draw_face_bounding_box(self, frame, face_locations):
        """
        Draw bounding boxes around detected faces
        
        Args:
            frame: numpy array representing the image frame
            face_locations: List of face locations
            
        Returns:
            numpy array: Frame with bounding boxes drawn
        """
        for (top, right, bottom, left) in face_locations:
            # Draw a box around the face
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            
            # Draw ROI rectangle on forehead
            forehead_top = max(0, top - int((bottom - top) * 0.1))
            forehead_bottom = top + int((bottom - top) * 0.3)
            forehead_left = left + int((right - left) * 0.2)
            forehead_right = right - int((right - left) * 0.2)
            cv2.rectangle(frame, (forehead_left, forehead_top), (forehead_right, forehead_bottom), (255, 0, 0), 2)
        
        return frame
    
    def process_frame(self, frame):
        """
        Process a single frame for face detection and ROI extraction
        
        Args:
            frame: numpy array representing the image frame
            
        Returns:
            tuple: (frame with bounding boxes, list of ROIs)
        """
        # Resize frame of video to 1/4 size for faster face detection processing
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        
        # Detect faces in the small frame
        face_locations = self.detect_faces(small_frame)
        
        # Scale back up face locations since the frame we detected in was scaled to 1/4 size
        face_locations = [(top * 4, right * 4, bottom * 4, left * 4) for (top, right, bottom, left) in face_locations]
        
        # Extract ROIs for each face
        rois = []
        for face_location in face_locations:
            roi = self.extract_roi(frame, face_location)
            rois.append(roi)
        
        # Draw bounding boxes on the frame
        frame_with_boxes = self.draw_face_bounding_box(frame.copy(), face_locations)
        
        return frame_with_boxes, rois
    
    def decode_image(self, image_data):
        """
        Decode base64 image data to numpy array
        
        Args:
            image_data: str, base64 encoded image data
            
        Returns:
            numpy array: Decoded image frame
        """
        import base64
        from io import BytesIO
        import PIL.Image as Image
        
        # Remove data URL prefix if present
        if image_data.startswith('data:image'):
            image_data = image_data.split(',')[1]
        
        # Decode base64 to bytes
        image_bytes = base64.b64decode(image_data)
        
        # Convert bytes to numpy array
        image = Image.open(BytesIO(image_bytes))
        frame = np.array(image)
        
        # Convert RGB to BGR if needed (OpenCV uses BGR)
        if frame.shape[-1] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        return frame
