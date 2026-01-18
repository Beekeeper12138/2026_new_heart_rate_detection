import cv2
import numpy as np
import time
import torch
import torchvision.transforms as transforms
from torch.autograd import Variable
import sys
import os

# Add rPPG directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../rPPG'))

# Try to import skin segmentation modules
try:
    from FaceSeg import FaceSegGPU
    from models import UNet16, UNet11
    SKIN_SEGMENTATION_AVAILABLE = True
except ImportError as e:
    print(f"Skin segmentation module import error: {e}")
    SKIN_SEGMENTATION_AVAILABLE = False

class FaceRecognitionService:
    def __init__(self):
        self.face_locations = []
        self.face_encodings = []
        self.face_names = []
        self.process_this_frame = True
        
        # Load Haar cascade for face detection (built-in OpenCV)
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # Check if cascade loaded successfully
        if self.face_cascade.empty():
            print(f"Error: Could not load face cascade from {cascade_path}")
            # Try alternative path
            import os
            alternative_paths = [
                'haarcascade_frontalface_default.xml',
                './haarcascade_frontalface_default.xml',
                '../haarcascade_frontalface_default.xml'
            ]
            
            for path in alternative_paths:
                if os.path.exists(path):
                    self.face_cascade = cv2.CascadeClassifier(path)
                    print(f"Successfully loaded cascade from alternative path: {path}")
                    break
            
            if self.face_cascade.empty():
                print("Critical error: No face cascade found. Face detection will not work.")
        
        # Initialize skin segmentation model if available
        self.skin_segmenter = None
        self.skin_segmentation_available = SKIN_SEGMENTATION_AVAILABLE
        
        if SKIN_SEGMENTATION_AVAILABLE:
            try:
                # Check if CUDA is available
                device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
                print(f"Initializing skin segmentation model on {device}")
                
                # Initialize skin segmentation model with compression
                self.skin_segmenter = FaceSegGPU(bs=1, size=256, use_compression=True)
                print("Skin segmentation model initialized successfully with compression")
                
                # Initialize image transform
                self.transform = transforms.Compose([
                    transforms.ToPILImage(),
                    transforms.Resize((256, 256)),
                    transforms.ToTensor(),
                    transforms.Normalize(
                        mean=[0.485, 0.456, 0.406],
                        std=[0.229, 0.224, 0.225]
                    )
                ])
            except Exception as e:
                print(f"Error initializing skin segmentation model: {e}")
                self.skin_segmentation_available = False
                self.skin_segmenter = None
    
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
        
        # 7. Multi-pass detection approach with optimized parameters
        # First pass: Balanced detection for normal conditions
        faces1 = self.face_cascade.detectMultiScale(
            edge_enhanced,
            scaleFactor=1.1,  # More conservative scale factor
            minNeighbors=5,   # Higher threshold to reduce false positives
            minSize=(30, 30), # Minimum face size to filter small false positives
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # Second pass: Sensitive detection for better coverage
        faces2 = self.face_cascade.detectMultiScale(
            edge_enhanced,
            scaleFactor=1.05,  # Moderately sensitive
            minNeighbors=3,    # Balanced threshold
            minSize=(20, 20),  # Detect smaller faces
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # Combine results from both passes, removing duplicates
        faces = []
        all_faces = list(faces1) + list(faces2)
        
        # Remove duplicate faces with improved logic
        for (x, y, w, h) in all_faces:
            duplicate = False
            # Calculate face area to filter very small false positives
            face_area = w * h
            if face_area < 400:  # Filter very small detections (20x20)
                continue
            
            for (x2, y2, w2, h2) in faces:
                # Check if centers are close (within 30% of face width/height)
                center_dist = ((x + w/2 - (x2 + w2/2)) ** 2 + (y + h/2 - (y2 + h2/2)) ** 2) ** 0.5
                if center_dist < min(w, h) * 0.3:
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
    
    def segment_skin(self, frame):
        """
        Segment skin pixels from the frame using deep learning
        
        Args:
            frame: numpy array representing the image frame
            
        Returns:
            numpy array: Skin mask (1 for skin, 0 for non-skin)
        """
        if not self.skin_segmentation_available or self.skin_segmenter is None:
            return None
        
        try:
            # Enhance contrast to improve skin segmentation in varying lighting
            enhanced_frame = frame.copy()
            
            # Apply illumination normalization if available
            if hasattr(self.skin_segmenter, 'normalize_illumination'):
                enhanced_frame = self.skin_segmenter.normalize_illumination(enhanced_frame)
            
            # Apply contrast enhancement if available
            if hasattr(self.skin_segmenter, 'enhance_contrast'):
                enhanced_frame = self.skin_segmenter.enhance_contrast(enhanced_frame)
            
            # Convert frame to RGB format (OpenCV uses BGR)
            frame_rgb = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2RGB)
            
            # Apply transform
            transformed = self.transform(frame_rgb)
            transformed = transformed.unsqueeze(0)  # Add batch dimension
            
            # Get skin mask with adaptive threshold
            mask = self.skin_segmenter.get_mask(transformed, frame.shape, adaptive_threshold=True)
            
            # Ensure mask shape matches frame shape
            if len(mask.shape) == 2:
                mask = np.expand_dims(mask, axis=2)
                mask = np.repeat(mask, 3, axis=2)
            
            return mask
        except Exception as e:
            print(f"Error in skin segmentation: {e}")
            return None
    
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
        
        # Ensure coordinates are in correct order
        if forehead_left >= forehead_right or forehead_top >= forehead_bottom:
            # If ROI is invalid, return a small central region
            center_x = (left + right) // 2
            center_y = (top + bottom) // 2
            roi_size = min(right - left, bottom - top) // 2
            forehead_top = max(0, center_y - roi_size // 2)
            forehead_bottom = min(h, center_y + roi_size // 2)
            forehead_left = max(0, center_x - roi_size // 2)
            forehead_right = min(w, center_x + roi_size // 2)
        
        # Extract ROI
        roi = frame[forehead_top:forehead_bottom, forehead_left:forehead_right]
        
        # Apply skin segmentation if available
        if self.skin_segmentation_available and self.skin_segmenter is not None:
            try:
                # Get skin mask for the entire frame
                skin_mask = self.segment_skin(frame)
                if skin_mask is not None:
                    # Extract mask for the ROI region
                    roi_mask = skin_mask[forehead_top:forehead_bottom, forehead_left:forehead_right]
                    # Ensure mask shape matches ROI shape
                    if roi_mask.shape == roi.shape:
                        roi = roi * roi_mask
            except Exception as e:
                print(f"Error applying skin mask to ROI: {e}")
        
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
            # Draw a red box around the face (red color: (0, 0, 255) in BGR format)
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
        
        return frame
    
    def process_frame(self, frame):
        """
        Process a single frame for face detection and ROI extraction
        
        Args:
            frame: numpy array representing the image frame
            
        Returns:
            tuple: (frame with bounding boxes, list of ROIs, list of face locations, processing resolution)
        """
        # Start timing
        start_time = time.time()
        
        # Get original frame resolution
        original_height, original_width = frame.shape[:2]
        
        # Check if frame is low resolution
        is_low_res = original_width < 640 or original_height < 480
        
        # Apply image enhancement for low resolution frames
        if is_low_res:
            # Resize to improve face detection
            scale_factor = max(640 / original_width, 480 / original_height)
            new_width = int(original_width * scale_factor)
            new_height = int(original_height * scale_factor)
            enhanced_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
            
            # Apply sharpening filter
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            enhanced_frame = cv2.filter2D(enhanced_frame, -1, kernel)
            
            # Apply histogram equalization to improve contrast
            if len(enhanced_frame.shape) == 3:
                # For color images, apply CLAHE to each channel
                channels = cv2.split(enhanced_frame)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                for i in range(len(channels)):
                    channels[i] = clahe.apply(channels[i])
                enhanced_frame = cv2.merge(channels)
            else:
                # For grayscale images
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                enhanced_frame = clahe.apply(enhanced_frame)
        else:
            enhanced_frame = frame.copy()
        
        # Resize frame of video for faster face detection processing
        # For low res, use smaller scale factor to preserve details
        scale_factor = 0.25 if not is_low_res else 0.5
        small_frame = cv2.resize(enhanced_frame, (0, 0), fx=scale_factor, fy=scale_factor)
        
        # Detect faces in the small frame
        face_locations = self.detect_faces(small_frame)
        
        # Calculate scale factor for face locations
        location_scale = 1 / scale_factor
        
        # Scale back up face locations
        face_locations = [(int(top * location_scale), int(right * location_scale), int(bottom * location_scale), int(left * location_scale)) for (top, right, bottom, left) in face_locations]
        
        # Ensure face locations are within bounds of original frame
        adjusted_face_locations = []
        for (top, right, bottom, left) in face_locations:
            # Adjust to original frame size if we scaled up for low res
            if is_low_res:
                adj_top = int(top * (original_height / new_height))
                adj_right = int(right * (original_width / new_width))
                adj_bottom = int(bottom * (original_height / new_height))
                adj_left = int(left * (original_width / new_width))
            else:
                adj_top, adj_right, adj_bottom, adj_left = top, right, bottom, left
            
            # Ensure bounds are within frame
            adj_top = max(0, adj_top)
            adj_right = min(original_width, adj_right)
            adj_bottom = min(original_height, adj_bottom)
            adj_left = max(0, adj_left)
            
            adjusted_face_locations.append((adj_top, adj_right, adj_bottom, adj_left))
        
        # Extract ROIs for each face
        rois = []
        
        # Try skin segmentation if available and needed
        skin_mask = None
        if self.skin_segmentation_available and len(adjusted_face_locations) > 0:
            try:
                skin_mask = self.segment_skin(enhanced_frame if is_low_res else frame)
            except Exception as e:
                print(f"Skin segmentation error: {e}")
        
        for face_location in adjusted_face_locations:
            roi = self.extract_roi(enhanced_frame if is_low_res else frame, face_location)
            rois.append(roi)
        
        # Face bounding boxes drawing disabled per user request
        # Draw bounding boxes on the frame
        display_frame = enhanced_frame if is_low_res else frame
        # frame_with_boxes = self.draw_face_bounding_box(display_frame.copy(), adjusted_face_locations)
        # Return original frame without bounding boxes
        frame_with_boxes = display_frame.copy()
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Print processing time for debugging
        if processing_time > 30:  # If processing time exceeds 33ms (30fps)
            print(f"Processing time: {processing_time:.2f}ms")
        
        return frame_with_boxes, rois, adjusted_face_locations, (original_width, original_height)
    
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
        
        # Debug: Print original image size
        print(f"Original image size: {image.width} x {image.height}")
        
        # Resize image to improve face detection
        # For better face detection, use at least 640x480 resolution
        min_width = 640
        min_height = 480
        
        if image.width < min_width or image.height < min_height:
            # Calculate new size while maintaining aspect ratio
            aspect_ratio = image.width / image.height
            if aspect_ratio > 1:
                # Landscape orientation
                new_width = min_width
                new_height = int(min_width / aspect_ratio)
            else:
                # Portrait orientation
                new_height = min_height
                new_width = int(min_height * aspect_ratio)
            
            # Resize image
            image = image.resize((new_width, new_height), Image.LANCZOS)
            print(f"Resized image to: {new_width} x {new_height}")
        
        frame = np.array(image)
        
        # Debug: Print final frame shape
        print(f"Final frame shape: {frame.shape}")
        
        # Convert RGB to BGR if needed (OpenCV uses BGR)
        if frame.shape[-1] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        return frame
    
    def encode_image(self, frame, format='PNG'):
        """
        Encode numpy array frame to base64 string
        
        Args:
            frame: numpy array representing the image frame
            format: str, encoding format ('PNG' for lossless, 'JPEG' for lossy)
            
        Returns:
            str: Base64 encoded image data
        """
        import base64
        from io import BytesIO
        import PIL.Image as Image
        
        # Convert BGR to RGB if needed (OpenCV uses BGR)
        if frame.shape[-1] == 3:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Convert numpy array to PIL Image
        image = Image.fromarray(frame)
        
        # Save image to bytes buffer
        buffer = BytesIO()
        if format.upper() == 'PNG':
            # Use PNG for lossless compression
            image.save(buffer, format='PNG')
            mime_type = 'image/png'
        else:
            # Use JPEG for lossy compression with high quality
            image.save(buffer, format='JPEG', quality=95)
            mime_type = 'image/jpeg'
        
        # Encode to base64
        image_bytes = buffer.getvalue()
        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        
        # Add data URL prefix
        return f"data:{mime_type};base64,{base64_data}"
