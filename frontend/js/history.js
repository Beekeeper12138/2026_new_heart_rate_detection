// History page application
class HistoryApp {
    constructor() {
        // Initialize UI manager
        this.uiManager = new UIManager();
        
        // Load history data on page load
        this.loadHistory();
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
                    this.addHistoryItem(record);
                });
                
                // Update record count
                document.getElementById('record-count').textContent = result.data.length;
                
                // Calculate and update statistics
                this.updateStatistics(result.data);
            }
        } catch (error) {
            console.error('Error loading history:', error);
            this.uiManager.showError('加载历史数据失败');
        }
    }
    
    addHistoryItem(record) {
        /*
        Add a history item to the list
        */
        const historyList = document.getElementById('history-list');
        const item = document.createElement('div');
        item.className = 'history-item';
        
        // Format timestamp
        const timestamp = new Date(record.timestamp);
        const formattedTime = timestamp.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        
        item.innerHTML = `
            <div class="history-item-content">
                <div class="history-item-heart-rate">${record.heart_rate} BPM</div>
                <div class="history-item-meta">
                    <span class="history-item-time">${formattedTime}</span>
                    <span class="history-item-device">${record.device_type || '未知设备'}</span>
                </div>
            </div>
        `;
        
        historyList.appendChild(item);
    }
    
    updateStatistics(data) {
        /*
        Calculate and update statistics from historical data
        */
        if (data.length === 0) return;
        
        const heartRates = data.map(record => record.heart_rate);
        
        // Calculate statistics
        const average = heartRates.reduce((sum, hr) => sum + hr, 0) / heartRates.length;
        const max = Math.max(...heartRates);
        const min = Math.min(...heartRates);
        
        // Update UI
        document.getElementById('avg-hr').textContent = Math.round(average);
        document.getElementById('max-hr').textContent = Math.round(max);
        document.getElementById('min-hr').textContent = Math.round(min);
    }
}

// Initialize the application when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', () => {
    window.historyApp = new HistoryApp();
});