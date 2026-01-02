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
        this.maxSignalData = 150; // Maximum number of data points to display (increased for more detail)
        
        // Heart rate history for stats calculation
        this.heartRateHistory = [];
        this.maxHeartRateHistory = 50;
        
        // Chart configuration - ECG style
        this.chartConfig = {
            gridColor: '#e0e0e0',
            ecgColor: '#e74c3c', // ECG red color
            ecgLineWidth: 2,
            background: '#fafafa',
            gridSpacing: 20, // Grid line spacing in pixels
            padding: 70, // Significantly increased left padding for Y-axis labels and title
            yAxisScale: 0.8, // Scale factor for Y axis (reduced to provide more vertical space)
            smoothFactor: 1.0, // Signal smoothing factor
            yAxisLabels: true, // Show Y-axis labels
            yAxisLabelStep: 5, // Show every 5th grid line label
            showMinMaxAvg: false // Temporarily disable Min/Max/Avg display to avoid overlap
        };
        
        // Initialize chart only if signal chart element exists
        if (this.signalCtx) {
            this._initChart();
        }
    }
    
    _initChart() {
        /*
        Initialize the signal chart with ECG style grid and Y-axis labels
        */
        const ctx = this.signalCtx;
        const width = this.signalChartElement.width;
        const height = this.signalChartElement.height;
        const config = this.chartConfig;
        
        // Clear canvas with background color
        ctx.fillStyle = config.background;
        ctx.fillRect(0, 0, width, height);
        
        // Draw grid - ECG style
        ctx.strokeStyle = config.gridColor;
        ctx.lineWidth = 0.5;
        
        // Draw vertical grid lines
        for (let x = config.padding; x <= width; x += config.gridSpacing) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        
        // Draw horizontal grid lines and Y-axis labels
        ctx.fillStyle = '#666666';
        ctx.font = '10px Arial';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        
        const yAxisLabels = [];
        // Start from a bit below the top and end a bit above the bottom to ensure labels are visible
        const startY = config.gridSpacing;
        const endY = height - config.gridSpacing;
        
        for (let y = startY; y <= endY; y += config.gridSpacing) {
            // Draw grid line
            ctx.strokeStyle = config.gridColor;
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(config.padding, y);
            ctx.lineTo(width, y);
            ctx.stroke();
            
            // Draw Y-axis label every N steps
            if (config.yAxisLabels && y % (config.gridSpacing * config.yAxisLabelStep) === 0) {
                // Calculate approximate signal value for this grid line
                const value = Math.round(100 - ((y - startY) / (endY - startY)) * 100);
                yAxisLabels.push({y: y, value: value});
                
                // Draw label with more space from the Y-axis
                ctx.fillStyle = '#666666';
                ctx.fillText(value.toString(), config.padding - 10, y);
            }
        }
        
        // Draw axes
        ctx.strokeStyle = '#95a5a6';
        ctx.lineWidth = 1;
        
        // X axis (horizontal)
        const midY = Math.round(height / 2);
        ctx.beginPath();
        ctx.moveTo(config.padding, midY);
        ctx.lineTo(width, midY);
        ctx.stroke();
        
        // Y axis (vertical) - left border
        ctx.beginPath();
        ctx.moveTo(config.padding, 0);
        ctx.lineTo(config.padding, height);
        ctx.stroke();
        
        // Draw Y-axis title
        ctx.save();
        // Move title further left and adjust rotation point to ensure full visibility
        ctx.translate(config.padding / 4, height / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillStyle = '#333333';
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('信号强度', 0, 0);
        ctx.restore();
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
            // Ensure signal data is an array of numbers
            const validSignalData = signalData.filter(val => typeof val === 'number');
            
            if (validSignalData.length > 0) {
                // Add new signal data
                this.signalData = [...this.signalData, ...validSignalData];
                
                // Keep only the most recent data points
                if (this.signalData.length > this.maxSignalData) {
                    this.signalData = this.signalData.slice(-this.maxSignalData);
                }
                
                // Redraw the chart
                this._drawSignal();
            }
        }
    }
    
    _drawSignal() {
        /*
        Draw the signal chart with ECG style
        */
        if (!this.signalCtx || this.signalData.length < 2) return;
        
        const ctx = this.signalCtx;
        const width = this.signalChartElement.width;
        const height = this.signalChartElement.height;
        const config = this.chartConfig;
        const signalData = this.signalData;
        
        // Calculate min and max signal values for scaling
        const minSignal = Math.min(...signalData);
        const maxSignal = Math.max(...signalData);
        const signalRange = maxSignal - minSignal || 0.1;
        
        // Clear canvas and redraw grid
        this._initChart();
        
        // Calculate step size
        const stepX = (width - 2 * config.padding) / (signalData.length - 1);
        
        // Calculate vertical offset (center signal in canvas)
        const midY = height / 2;
        const yOffset = height * (1 - config.yAxisScale) / 2;
        
        // Draw Y-axis value markers (based on actual signal range) only if enabled
        if (config.showMinMaxAvg) {
            ctx.fillStyle = '#666666';
            ctx.font = '10px Arial';
            ctx.textAlign = 'right';
            ctx.textBaseline = 'middle';
            
            // Draw min/max/avg values
            const avgSignal = signalData.reduce((sum, val) => sum + val, 0) / signalData.length;
            const yAxisValues = [
                { label: `Max: ${maxSignal.toFixed(2)}`, y: height - yOffset },
                { label: `Avg: ${avgSignal.toFixed(2)}`, y: midY },
                { label: `Min: ${minSignal.toFixed(2)}`, y: yOffset }
            ];
            
            yAxisValues.forEach(item => {
                ctx.fillStyle = '#333333';
                ctx.fillText(item.label, config.padding - 5, item.y);
            });
        }
        
        // Draw signal line - ECG style
        ctx.strokeStyle = config.ecgColor;
        ctx.lineWidth = config.ecgLineWidth;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.beginPath();
        
        for (let i = 0; i < signalData.length; i++) {
            const x = config.padding + i * stepX;
            
            // Normalize signal value to 0-1 range
            const normalizedSignal = (signalData[i] - minSignal) / signalRange;
            
            // Scale to canvas height with padding and center alignment
            const y = height - yOffset - normalizedSignal * height * config.yAxisScale;
            
            // Draw the point - use simple line for better performance and clarity
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
        
        // Draw signal fill for better visual effect
        ctx.fillStyle = 'rgba(231, 76, 60, 0.1)'; // Semi-transparent red fill
        ctx.lineTo(width - config.padding, height - yOffset);
        ctx.lineTo(config.padding, height - yOffset);
        ctx.closePath();
        ctx.fill();
        
        // Add a simple moving dot at the end of the signal to show real-time update
        if (signalData.length > 0) {
            const lastIndex = signalData.length - 1;
            const x = config.padding + lastIndex * stepX;
            const normalizedSignal = (signalData[lastIndex] - minSignal) / signalRange;
            const y = height - yOffset - normalizedSignal * height * config.yAxisScale;
            
            ctx.fillStyle = '#2ecc71'; // Green dot for real-time indicator
            ctx.beginPath();
            ctx.arc(x, y, 3, 0, 2 * Math.PI);
            ctx.fill();
        }
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
