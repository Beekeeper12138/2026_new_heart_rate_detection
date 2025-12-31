class CameraManager {
    constructor(videoElement, canvasElement) {
        this.video = videoElement;
        this.canvas = canvasElement;
        this.ctx = canvas.getContext('2d');
        this.stream = null;
        this.isStreaming = false;
        this.frameCallback = null;
    }

    async start() {
        /*
        Start the camera and begin streaming
        */
        try {
            // Request camera access
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 640 },
                    height: { ideal: 480 },
                    facingMode: 'user'  // Use front-facing camera
                },
                audio: false
            });

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
        } catch (error) {
            console.error('Error accessing camera:', error);
            throw new Error('无法访问摄像头，请确保已授予摄像头权限');
        }
    }

    stop() {
        /*
        Stop the camera and streaming
        */
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
            this.isStreaming = false;
        }
    }

    _captureFrames() {
        /*
        Capture frames from the video stream at regular intervals
        */
        if (!this.isStreaming) return;

        // Draw current frame to canvas
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

        // Call the frame callback if it exists
        if (this.frameCallback) {
            this.frameCallback();
        }

        // Capture next frame
        requestAnimationFrame(() => this._captureFrames());
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

        // Ensure canvas dimensions match video
        this.canvas.width = this.video.videoWidth;
        this.canvas.height = this.video.videoHeight;

        // Draw current frame to canvas
        this.ctx.drawImage(this.video, 0, 0, this.canvas.width, this.canvas.height);

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
