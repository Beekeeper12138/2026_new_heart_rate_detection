class WebSocketManager {
    constructor(url) {
        this.url = url;
        this.socket = null;
        this.isConnected = false;
        this.callbacks = {
            onOpen: null,
            onClose: null,
            onMessage: null,
            onError: null
        };
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000; // 1 second
        this.frameInterval = null;
    }

    connect() {
        /*
        Connect to the WebSocket server
        */
        try {
            this.socket = new WebSocket(this.url);

            this.socket.onopen = (event) => {
                this.isConnected = true;
                this.reconnectAttempts = 0;
                if (this.callbacks.onOpen) {
                    this.callbacks.onOpen(event);
                }
            };

            this.socket.onmessage = (event) => {
                if (this.callbacks.onMessage) {
                    try {
                        const data = JSON.parse(event.data);
                        this.callbacks.onMessage(data);
                    } catch (error) {
                        console.error('Error parsing WebSocket message:', error);
                    }
                }
            };

            this.socket.onclose = (event) => {
                this.isConnected = false;
                if (this.callbacks.onClose) {
                    this.callbacks.onClose(event);
                }

                // Attempt to reconnect if not manually closed
                if (!event.wasClean && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this._reconnect();
                }
            };

            this.socket.onerror = (error) => {
                if (this.callbacks.onError) {
                    this.callbacks.onError(error);
                }
            };
        } catch (error) {
            console.error('Error connecting to WebSocket:', error);
            throw new Error('无法连接到服务器');
        }
    }

    _reconnect() {
        /*
        Attempt to reconnect to the WebSocket server
        */
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
        
        setTimeout(() => {
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            this.connect();
        }, delay);
    }

    disconnect() {
        /*
        Disconnect from the WebSocket server
        */
        if (this.socket) {
            this.socket.close(1000, 'Manual disconnect');
            this.socket = null;
            this.isConnected = false;
        }
    }

    send(data) {
        /*
        Send data to the WebSocket server
        
        Args:
            data: Data to send (string or object)
        */
        if (!this.isConnected || !this.socket) {
            console.error('WebSocket is not connected');
            return false;
        }

        try {
            const message = typeof data === 'string' ? data : JSON.stringify(data);
            this.socket.send(message);
            return true;
        } catch (error) {
            console.error('Error sending WebSocket message:', error);
            return false;
        }
    }

    startSendingFrames(cameraManager, interval = 100) {
        /*
        Start sending frames from the camera to the server at regular intervals
        
        Args:
            cameraManager: CameraManager instance
            interval: Interval in milliseconds between frame sends
        */
        this.stopSendingFrames();
        
        this.frameInterval = setInterval(() => {
            if (this.isConnected && cameraManager.getIsStreaming()) {
                const frame = cameraManager.getFrame();
                if (frame) {
                    this.send(frame);
                }
            }
        }, interval);
    }

    stopSendingFrames() {
        /*
        Stop sending frames to the server
        */
        if (this.frameInterval) {
            clearInterval(this.frameInterval);
            this.frameInterval = null;
        }
    }

    onOpen(callback) {
        /*
        Set callback for WebSocket open event
        
        Args:
            callback: Function to call when WebSocket opens
        */
        this.callbacks.onOpen = callback;
    }

    onClose(callback) {
        /*
        Set callback for WebSocket close event
        
        Args:
            callback: Function to call when WebSocket closes
        */
        this.callbacks.onClose = callback;
    }

    onMessage(callback) {
        /*
        Set callback for WebSocket message event
        
        Args:
            callback: Function to call when WebSocket receives a message
        */
        this.callbacks.onMessage = callback;
    }

    onError(callback) {
        /*
        Set callback for WebSocket error event
        
        Args:
            callback: Function to call when WebSocket encounters an error
        */
        this.callbacks.onError = callback;
    }

    getIsConnected() {
        /*
        Check if WebSocket is connected
        
        Returns:
            boolean: True if connected, False otherwise
        */
        return this.isConnected;
    }
}
