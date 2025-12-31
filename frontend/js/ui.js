class UIManager {
    constructor() {
        // DOM elements - handle cases where elements might not exist on all pages
        this.heartRateElement = document.getElementById('heart-rate');
        this.statusElement = document.getElementById('status');
        this.signalChartElement = document.getElementById('signal-chart');
        this.faceCountElement = document.getElementById('face-count');
        this.avgHrElement = document.getElementById('avg-hr');
        this.minHrElement = document.getElementById('min-hr');
        this.maxHrElement = document.getElementById('max-hr');
        this.historyListElement = document.getElementById('history-list');
        this.startBtn = document.getElementById('start-btn');
        this.stopBtn = document.getElementById('stop-btn');
        
        // Chart context - only initialize if signal chart element exists
        this.signalCtx = this.signalChartElement ? this.signalChartElement.getContext('2d') : null;
        
        // Signal data
        this.signalData = [];
        this.maxSignalData = 100; // Maximum number of data points to display
        
        // Heart rate history for stats calculation
        this.heartRateHistory = [];
        this.maxHeartRateHistory = 50;
        
        // Initialize chart only if signal chart element exists
        if (this.signalCtx) {
            this._initChart();
        }
    }
    
    _initChart() {
        /*
        Initialize the signal chart
        */
        // Clear canvas
        this.signalCtx.clearRect(0, 0, this.signalChartElement.width, this.signalChartElement.height);
        
        // Draw grid
        this.signalCtx.strokeStyle = '#e0e0e0';
        this.signalCtx.lineWidth = 1;
        
        // Horizontal lines
        for (let i = 0; i <= 4; i++) {
            const y = (this.signalChartElement.height / 4) * i;
            this.signalCtx.beginPath();
            this.signalCtx.moveTo(0, y);
            this.signalCtx.lineTo(this.signalChartElement.width, y);
            this.signalCtx.stroke();
        }
    }
    
    updateHeartRate(heartRate) {
        /*
        Update the heart rate display
        
        Args:
            heartRate: number, Current heart rate in BPM
        */
        if (heartRate > 0) {
            this.heartRateElement.textContent = Math.round(heartRate);
            
            // Update heart rate history for stats
            this.heartRateHistory.push(heartRate);
            if (this.heartRateHistory.length > this.maxHeartRateHistory) {
                this.heartRateHistory.shift();
            }
            
            // Update stats
            this._updateStats();
        }
    }
    
    updateStatus(status) {
        /*
        Update the status message
        
        Args:
            status: string, Status message to display
        */
        this.statusElement.textContent = status;
    }
    
    updateSignal(signalData) {
        /*
        Update the signal chart with new data
        
        Args:
            signalData: array, Array of signal values
        */
        if (signalData && signalData.length > 0) {
            // Add new signal data
            this.signalData = [...this.signalData, ...signalData];
            
            // Keep only the most recent data points
            if (this.signalData.length > this.maxSignalData) {
                this.signalData = this.signalData.slice(-this.maxSignalData);
            }
            
            // Redraw the chart
            this._drawSignal();
        }
    }
    
    _drawSignal() {
        /*
        Draw the signal chart
        */
        if (!this.signalCtx || this.signalData.length < 2) return;
        
        // Clear canvas
        this.signalCtx.clearRect(0, 0, this.signalChartElement.width, this.signalChartElement.height);
        
        // Draw grid again
        this._initChart();
        
        // Calculate min and max signal values for scaling
        const minSignal = Math.min(...this.signalData);
        const maxSignal = Math.max(...this.signalData);
        const signalRange = maxSignal - minSignal || 1;
        
        // Calculate step size
        const stepX = this.signalChartElement.width / (this.signalData.length - 1);
        
        // Draw signal line
        this.signalCtx.strokeStyle = '#3498db';
        this.signalCtx.lineWidth = 2;
        this.signalCtx.beginPath();
        
        for (let i = 0; i < this.signalData.length; i++) {
            const x = i * stepX;
            // Scale signal value to canvas height (with some padding)
            const y = this.signalChartElement.height - ((this.signalData[i] - minSignal) / signalRange) * this.signalChartElement.height * 0.8 - this.signalChartElement.height * 0.1;
            
            if (i === 0) {
                this.signalCtx.moveTo(x, y);
            } else {
                this.signalCtx.lineTo(x, y);
            }
        }
        
        this.signalCtx.stroke();
    }
    
    updateFaceCount(count) {
        /*
        Update the face count display
        
        Args:
            count: number, Number of detected faces
        */
        this.faceCountElement.textContent = count;
    }
    
    _updateStats() {
        /*
        Update the heart rate statistics
        */
        if (this.heartRateHistory.length === 0) {
            this.avgHrElement.textContent = '--';
            this.minHrElement.textContent = '--';
            this.maxHrElement.textContent = '--';
            return;
        }
        
        const avg = this.heartRateHistory.reduce((sum, hr) => sum + hr, 0) / this.heartRateHistory.length;
        const min = Math.min(...this.heartRateHistory);
        const max = Math.max(...this.heartRateHistory);
        
        this.avgHrElement.textContent = Math.round(avg);
        this.minHrElement.textContent = Math.round(min);
        this.maxHrElement.textContent = Math.round(max);
    }
    
    addToHistory(heartRate) {
        /*
        Add a heart rate reading to the history list
        
        Args:
            heartRate: number, Heart rate to add to history
        */
        if (heartRate <= 0) return;
        
        // Only proceed if history list element exists
        if (!this.historyListElement) return;
        
        // Create history item element
        const historyItem = document.createElement('div');
        historyItem.className = 'history-item';
        
        const now = new Date();
        const timeString = now.toLocaleTimeString();
        
        historyItem.innerHTML = `
            <span class="history-time">${timeString}</span>
            <span class="history-hr">${Math.round(heartRate)} BPM</span>
        `;
        
        // Add to the beginning of the list
        this.historyListElement.insertBefore(historyItem, this.historyListElement.firstChild);
        
        // Remove "no data" message if it exists
        const noDataMsg = this.historyListElement.querySelector('p');
        if (noDataMsg) {
            noDataMsg.remove();
        }
        
        // Keep only the last 10 history items
        const historyItems = this.historyListElement.querySelectorAll('.history-item');
        if (historyItems.length > 10) {
            for (let i = 10; i < historyItems.length; i++) {
                historyItems[i].remove();
            }
        }
    }
    
    updateControls(isMonitoring) {
        /*
        Update control buttons based on monitoring status - only update buttons that exist
        
        Args:
            isMonitoring: boolean, Whether monitoring is active
        */
        if (this.startBtn) {
            this.startBtn.disabled = isMonitoring;
        }
        if (this.stopBtn) {
            this.stopBtn.disabled = !isMonitoring;
        }
    }
    
    reset() {
        /*
        Reset all UI elements to initial state - only update elements that exist
        */
        if (this.heartRateElement) this.heartRateElement.textContent = '--';
        if (this.statusElement) this.statusElement.textContent = '等待开始...';
        if (this.faceCountElement) this.faceCountElement.textContent = '0';
        if (this.avgHrElement) this.avgHrElement.textContent = '--';
        if (this.minHrElement) this.minHrElement.textContent = '--';
        if (this.maxHrElement) this.maxHrElement.textContent = '--';
        
        // Clear signal data and chart - only if signal context exists
        this.signalData = [];
        if (this.signalCtx) {
            this._initChart();
        }
        
        // Clear heart rate history
        this.heartRateHistory = [];
        
        // Update controls - only if buttons exist
        if (this.startBtn || this.stopBtn) {
            this.updateControls(false);
        }
    }
    
    showError(message) {
        /*
        Show an error message to the user
        
        Args:
            message: string, Error message to display
        */
        this.statusElement.textContent = `错误: ${message}`;
        this.statusElement.style.color = '#e74c3c';
        
        // Reset color after 3 seconds
        setTimeout(() => {
            this.statusElement.style.color = '';
        }, 3000);
    }
}
