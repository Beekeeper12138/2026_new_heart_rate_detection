// Main application
class HeartRateApp {
    constructor() {
        // Get DOM elements
        this.video = document.getElementById('video');
        this.canvas = document.getElementById('canvas');
        
        // Camera selection elements
        this.cameraSourceSelect = document.getElementById('camera-source');
        this.esp32IpInput = document.getElementById('esp32-ip');
        
        // Initialize managers
        this.cameraManager = new CameraManager(this.video, this.canvas);
        this.uiManager = new UIManager();
        
        // WebSocket URL (constructed based on current location)
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/heartrate`;
        this.webSocketManager = new WebSocketManager(wsUrl);
        
        // Application state
        this.isMonitoring = false;
        this.lastValidHeartRate = null;
        
        // Initialize event listeners
        this._initEventListeners();
        
        // Initialize WebSocket callbacks
        this._initWebSocketCallbacks();
        
        // Initialize UI
        this.uiManager.reset();
    }
    
    _initEventListeners() {
        /*
        Initialize event listeners for UI elements
        */
        // Start button click
        document.getElementById('start-btn').addEventListener('click', () => {
            this.startMonitoring();
        });
        
        // Stop button click
        document.getElementById('stop-btn').addEventListener('click', () => {
            this.stopMonitoring();
        });
        
        // Save button click
        document.getElementById('save-btn').addEventListener('click', () => {
            this.saveData();
        });
        
        // Camera source change
        if (this.cameraSourceSelect) {
            this.cameraSourceSelect.addEventListener('change', (event) => {
                // Stop monitoring if currently running
                if (this.isMonitoring) {
                    this.stopMonitoring();
                }
                
                // Update ESP32 IP input visibility based on selection
                if (event.target.value === 'esp32') {
                    this.esp32IpInput.style.display = 'inline-block';
                } else {
                    this.esp32IpInput.style.display = 'none';
                }
            });
        }
        
        // Initialize ESP32 IP input visibility based on default selection
        if (this.cameraSourceSelect && this.esp32IpInput) {
            if (this.cameraSourceSelect.value === 'esp32') {
                this.esp32IpInput.style.display = 'inline-block';
            } else {
                this.esp32IpInput.style.display = 'none';
            }
        }
    }
    
    _initWebSocketCallbacks() {
        /*
        Initialize WebSocket event callbacks
        */
        this.webSocketManager.onOpen(() => {
            console.log('WebSocket connected');
            this.uiManager.updateStatus('已连接到服务器');
        });
        
        this.webSocketManager.onClose(() => {
            console.log('WebSocket disconnected');
            if (this.isMonitoring) {
                this.uiManager.updateStatus('与服务器断开连接');
            }
        });
        
        this.webSocketManager.onMessage((data) => {
            this._handleWebSocketMessage(data);
        });
        
        this.webSocketManager.onError((error) => {
            console.error('WebSocket error:', error);
            this.uiManager.showError('WebSocket连接错误');
        });
    }
    
    async startMonitoring() {
        /*
        Start heart rate monitoring
        */
        try {
            // Get selected camera mode and IP address
            const cameraMode = this.cameraSourceSelect ? this.cameraSourceSelect.value : 'device';
            const esp32Ip = this.esp32IpInput ? this.esp32IpInput.value.trim() : '192.168.1.100';
            
            // Validate ESP32 IP if ESP32 mode is selected
            if (cameraMode === 'esp32' && !esp32Ip) {
                this.uiManager.showError('请输入ESP32 IP地址');
                return;
            }
            
            // Set camera mode
            this.cameraManager.setCameraMode(cameraMode, esp32Ip);
            
            // Start camera
            await this.cameraManager.start();
            this.uiManager.updateStatus('摄像头已启动，正在连接服务器...');
            
            // Connect to WebSocket server
            this.webSocketManager.connect();
            
            // Start sending frames after a short delay to ensure WebSocket connection is established
            setTimeout(() => {
                this.webSocketManager.startSendingFrames(this.cameraManager, 100); // Send frame every 100ms
                this.isMonitoring = true;
                this.uiManager.updateStatus('正在监测心率...');
                this.uiManager.updateControls(true);
            }, 500);
            
        } catch (error) {
            console.error('Error starting monitoring:', error);
            this.uiManager.showError(error.message);
        }
    }
    
    stopMonitoring() {
        /*
        Stop heart rate monitoring
        */
        // Stop sending frames
        this.webSocketManager.stopSendingFrames();
        
        // Disconnect WebSocket
        this.webSocketManager.disconnect();
        
        // Stop camera
        this.cameraManager.stop();
        
        // Update state
        this.isMonitoring = false;
        
        // Reset UI
        this.uiManager.reset();
    }
    
    _handleWebSocketMessage(data) {
        /*
        Handle WebSocket messages from the server
        
        Args:
            data: Object, Message data from server
        */
        if (data.status === 'success') {
            // Update heart rate if available
            if (data.heart_rates && data.heart_rates.length > 0) {
                const heartRate = data.heart_rates[0]; // Use first face's heart rate
                this.uiManager.updateHeartRate(heartRate);
                this.lastValidHeartRate = heartRate; // Store the last valid heart rate
            }
            
            // Update face count
            this.uiManager.updateFaceCount(data.num_faces || 0);
            
            // Update signal chart
            if (data.signal && data.signal.length > 0) {
                this.uiManager.updateSignal(data.signal);
            }
            
            // Update status based on face detection
            if (data.num_faces > 0) {
                this.uiManager.updateStatus('正在监测心率...');
            } else {
                this.uiManager.updateStatus('未检测到人脸，请调整位置...');
            }
        } else if (data.status === 'error') {
            console.error('Server error:', data.message);
            this.uiManager.showError(data.message);
        }
    }
    
    async saveData() {
        /*
        Save current heart rate data to server
        */
        try {
            let currentHeartRate;
            
            // Try to get heart rate from UI first (in case monitoring is still active)
            const uiHeartRate = parseInt(this.uiManager.heartRateElement.textContent);
            if (!isNaN(uiHeartRate) && uiHeartRate > 0) {
                currentHeartRate = uiHeartRate;
            } else if (this.lastValidHeartRate && this.lastValidHeartRate > 0) {
                // Use the last valid heart rate if UI is reset
                currentHeartRate = this.lastValidHeartRate;
            } else {
                this.uiManager.showError('没有可用的心率数据可保存');
                return;
            }
            
            // Determine device type
            const deviceType = this._getDeviceType();
            
            // Send POST request to save data
            const response = await fetch('/api/rppg/save', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: new URLSearchParams({
                    heart_rate: currentHeartRate,
                    device_type: deviceType
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                // Add to local history
                this.uiManager.addToHistory(currentHeartRate);
                this.uiManager.updateStatus('数据已保存');
            } else {
                this.uiManager.showError('保存数据失败');
            }
        } catch (error) {
            console.error('Error saving data:', error);
            this.uiManager.showError('保存数据时发生错误');
        }
    }
    
    _getDeviceType() {
        /*
        Determine the device type (desktop or mobile)
        
        Returns:
            string: Device type ('desktop' or 'mobile')
        */
        const userAgent = navigator.userAgent;
        if (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(userAgent)) {
            return 'mobile';
        }
        return 'desktop';
    }
    
    async loadHistory() {
        /*
        Load historical heart rate data from server
        */
        try {
            const response = await fetch('/api/rppg/history');
            const result = await response.json();
            
            if (result.status === 'success' && result.data.length > 0) {
                // Clear current history
                const historyList = document.getElementById('history-list');
                historyList.innerHTML = '';
                
                // Add each historical record
                result.data.forEach(record => {
                    this.uiManager.addToHistory(record.heart_rate);
                });
            }
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }
}

// Initialize the application when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    window.heartRateApp = new HeartRateApp();
});
