class CameraManager {
    constructor(videoElement, canvasElement) {
        this.video = videoElement;
        this.canvas = canvasElement;
        this.ctx = canvas.getContext('2d');
        this.stream = null;
        this.isStreaming = false;
        this.frameCallback = null;
        this.cameraMode = 'device'; // Default to device camera
        this.esp32Ip = '192.168.1.100'; // Default ESP32 IP address
        this.esp32StreamUrl = '';
        this.esp32Image = new Image();
        this.esp32StreamInterval = null;
        this.rafId = null; // Initialize requestAnimationFrame ID
    }

    setCameraMode(mode, ip = '192.168.1.100') {
        /*
        Set the camera mode
        
        Args:
            mode: string, 'device' for device camera or 'esp32' for ESP32 camera
            ip: string, ESP32 IP address (required if mode is 'esp32')
        */
        // Stop current stream before changing mode
        this.stop();
        
        this.cameraMode = mode;
        if (mode === 'esp32') {
            this.esp32Ip = ip;
            this.esp32StreamUrl = `http://${ip}/stream`;
        }
    }

    async start() {
        /*
        Start the camera and begin streaming based on selected mode
        */
        try {
            if (this.cameraMode === 'device') {
                // Device camera mode
                return await this._startDeviceCamera();
            } else if (this.cameraMode === 'esp32') {
                // ESP32 camera mode
                return await this._startEsp32Camera();
            }
        } catch (error) {
            console.error('Error starting camera:', error);
            throw new Error('无法启动摄像头: ' + error.message);
        }
    }

    async _startDeviceCamera() {
        /*
        Start the device camera
        */
        // Request camera access
        this.stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                facingMode: 'user'  // Use front-facing camera
            },
            audio: false
        });

        // Make video visible and canvas hidden
        this.video.style.display = 'block';
        this.canvas.style.display = 'none';

        // Set the video source
        this.video.srcObject = this.stream;
        this.isStreaming = true;

        // Wait for the video to start playing
        await new Promise((resolve) => {
            this.video.onloadedmetadata = () => {
                resolve();
            };
        });

        // Start capturing frames
        this._captureFrames();

        return true;
    }

    async _startEsp32Camera() {
        /*
        Start the ESP32 camera stream
        */
        try {
            // Clear any existing video stream
            if (this.video.srcObject) {
                this.video.srcObject = null;
            }
            
            // Make canvas visible and disable video
            this.video.style.display = 'none';
            this.canvas.style.display = 'block';
            
            this.isStreaming = true;
            
            // Start capturing frames from ESP32 stream
            this._captureEsp32Frames();
            
            return true;
        } catch (error) {
            console.error('Error starting ESP32 camera:', error);
            throw new Error('无法连接到ESP32摄像头，请检查IP地址和网络连接');
        }
    }

    stop() {
        /*
        Stop the camera and streaming - stop all possible streams and timers
        */
        this.isStreaming = false;
        
        // Stop device camera stream regardless of current mode
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
        
        // Stop ESP32 camera stream regardless of current mode
        if (this.esp32StreamInterval) {
            clearInterval(this.esp32StreamInterval);
            this.esp32StreamInterval = null;
        }
        
        // Clear any pending requestAnimationFrame for device camera
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
    }

    _captureFrames() {
        /*
        Capture frames from the video stream at regular intervals
        */
        if (!this.isStreaming) return;

        if (this.cameraMode === 'device') {
            // Draw current frame from device camera
            this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        }

        // Call the frame callback if it exists
        if (this.frameCallback) {
            this.frameCallback();
        }

        // Capture next frame and store the requestAnimationFrame ID
        this.rafId = requestAnimationFrame(() => this._captureFrames());
    }

    _captureEsp32Frames() {
        /*
        Capture frames from ESP32 MJPEG stream
        */
        if (!this.isStreaming) return;
        
        // Create a new image object for each frame to avoid caching issues
        const img = new Image();
        img.crossOrigin = 'anonymous';
        
        // Use a unique URL to prevent caching
        const streamUrl = `${this.esp32StreamUrl}?t=${Date.now()}`;
        
        img.onload = () => {
            // Draw the ESP32 frame to canvas
            if (this.isStreaming) {
                // Resize to match canvas dimensions (640x480)
                this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
                
                // Call frame callback if it exists
                if (this.frameCallback) {
                    this.frameCallback();
                }
            }
        };
        
        img.onerror = (error) => {
            console.error('Error loading ESP32 frame:', error);
            if (this.isStreaming) {
                // Try again in 100ms
                setTimeout(() => this._captureEsp32Frames(), 100);
                return;
            }
        };
        
        // Set the image source to the ESP32 stream URL
        img.src = streamUrl;
        
        // Continue capturing frames
        if (this.isStreaming) {
            this.esp32StreamInterval = setTimeout(() => this._captureEsp32Frames(), 33); // ~30fps
        }
    }

    getFrame() {
        /*
        Get the current frame from the canvas as a base64 encoded string
        
        Returns:
            string: Base64 encoded image data
        */
        if (!this.isStreaming) {
            return null;
        }

        // Ensure canvas has proper dimensions
        if (this.canvas.width === 0 || this.canvas.height === 0) {
            this.canvas.width = 640;
            this.canvas.height = 480;
        }

        // For ESP32 mode, the frame is already drawn to canvas by _captureEsp32Frames
        // For device mode, draw current frame if needed
        if (this.cameraMode === 'device') {
            // Draw current frame to canvas
            this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);
        }

        // Convert canvas to base64 image
        return this.canvas.toDataURL('image/jpeg', 0.7); // 70% quality for better performance
    }

    onFrame(callback) {
        /*
        Set a callback to be called for each captured frame
        
        Args:
            callback: Function to be called with each frame
        */
        this.frameCallback = callback;
    }

    getIsStreaming() {
        /*
        Check if the camera is currently streaming
        
        Returns:
            boolean: True if streaming, False otherwise
        */
        return this.isStreaming;
    }

    flipCamera() {
        /*
        Flip between front and back cameras (if available)
        */
        // This is a simplified implementation
        // In a real app, you'd enumerate devices and select the appropriate camera
        this.stop();
        return this.start();
    }
}
