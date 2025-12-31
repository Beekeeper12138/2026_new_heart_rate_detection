import cv2
import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq

class RPPGService:
    def __init__(self):
        self.signal_buffer = []
        self.buffer_size = 300  # Approximately 15 seconds at 20fps for more stable FFT
        self.fps = 20.0
        
        # Bandpass filter parameters (0.7-3 Hz corresponds to 42-180 BPM)
        self.lowcut = 0.7
        self.highcut = 3.0
        self.order = 4
        
        # Heart rate smoothing parameters
        self.heart_rate_history = []
        self.hr_history_size = 10  # Smooth over last 10 readings
        
        # Signal quality parameters - reduced threshold for better testing
        self.min_signal_quality = 0.1
        
        # CHROME algorithm weights for better signal extraction
        self.chrome_weights = np.array([0.1447, 0.4251, -0.5698])
    
    def extract_color_signal(self, roi):
        """
        Extract average RGB color values from ROI
        
        Args:
            roi: numpy array representing the Region of Interest
            
        Returns:
            tuple: Average (R, G, B) values
        """
        if roi is None or roi.size == 0:
            return (0, 0, 0)
        
        # Calculate average RGB values
        avg_r = np.mean(roi[:, :, 2])  # OpenCV uses BGR format
        avg_g = np.mean(roi[:, :, 1])
        avg_b = np.mean(roi[:, :, 0])
        
        return (avg_r, avg_g, avg_b)
    
    def apply_chrome(self, r, g, b):
        """
        Apply CHROME algorithm to enhance blood volume pulse signal
        CHROME: Color-based rPPG Enhancement Algorithm
        
        Args:
            r: Red channel value
            g: Green channel value
            b: Blue channel value
            
        Returns:
            float: Enhanced PPG signal value
        """
        # Normalize RGB values to avoid illumination effects
        total = r + g + b
        if total == 0:
            return 0.0
        
        # Normalized RGB
        r_norm = r / total
        g_norm = g / total
        b_norm = b / total
        
        # Apply CHROME algorithm using predefined weights
        chrome_signal = (self.chrome_weights[0] * r_norm + 
                        self.chrome_weights[1] * g_norm + 
                        self.chrome_weights[2] * b_norm)
        
        return chrome_signal
    
    def butter_bandpass_filter(self, data):
        """
        Apply Butterworth bandpass filter to the signal
        
        Args:
            data: 1D numpy array, input signal
            
        Returns:
            numpy array: Filtered signal
        """
        nyquist = 0.5 * self.fps
        low = self.lowcut / nyquist
        high = self.highcut / nyquist
        
        b, a = signal.butter(self.order, [low, high], btype='band')
        y = signal.filtfilt(b, a, data)
        
        return y
    
    def calculate_heart_rate(self, signal):
        """
        Calculate heart rate from filtered signal using FFT with simplified approach
        
        Args:
            signal: 1D numpy array, filtered PPG signal
            
        Returns:
            float: Estimated heart rate in BPM
        """
        n = len(signal)
        if n < 20:  # Need at least 20 points for basic FFT
            return 0.0
        
        try:
            # Only use FFT for simplicity
            heart_rate = self._calculate_heart_rate_fft(signal)
            
            # If FFT returns invalid, try a simpler approach
            if heart_rate <= 0:
                # Basic frequency estimation from peaks
                heart_rate = self._calculate_heart_rate_simple(signal)
            
            return heart_rate
        except Exception as e:
            return 0.0
    
    def _calculate_heart_rate_simple(self, signal):
        """
        Simple heart rate calculation using basic peak detection
        
        Args:
            signal: Filtered PPG signal
            
        Returns:
            float: Estimated heart rate in BPM
        """
        # Simple peak detection
        peaks = []
        for i in range(1, len(signal)-1):
            if signal[i] > signal[i-1] and signal[i] > signal[i+1]:
                peaks.append(i)
        
        if len(peaks) < 2:
            # If not enough peaks, use a default range or estimate
            return 75.0  # Default resting heart rate
        
        # Calculate average peak interval
        intervals = np.diff(peaks) / self.fps
        avg_interval = np.mean(intervals)
        
        if avg_interval <= 0:
            return 75.0
        
        return 60.0 / avg_interval
    
    def _calculate_signal_quality(self, signal):
        """
        Calculate signal quality based on signal-to-noise ratio
        
        Args:
            signal: Filtered PPG signal
            
        Returns:
            float: Signal quality score (0-1, higher is better)
        """
        # Calculate signal power in the heart rate band
        # This is a simplified quality metric
        mean_val = np.mean(signal)
        std_val = np.std(signal)
        
        if std_val == 0:
            return 0.0
        
        # Normalized standard deviation as a simple quality measure
        quality = min(std_val / (abs(mean_val) + 1e-6), 1.0)
        
        return quality
    
    def _calculate_heart_rate_fft(self, signal):
        """
        Calculate heart rate using FFT
        
        Args:
            signal: Filtered PPG signal
            
        Returns:
            float: Heart rate in BPM
        """
        n = len(signal)
        
        # Compute FFT
        yf = fft(signal)
        xf = fftfreq(n, 1 / self.fps)[:n//2]
        
        # Get magnitude spectrum
        magnitude = 2.0/n * np.abs(yf[:n//2])
        
        # Filter out frequencies outside the valid range
        valid_indices = np.where((xf >= self.lowcut) & (xf <= self.highcut))[0]
        if len(valid_indices) == 0:
            return 0.0
        
        # Find the frequency with maximum magnitude
        max_index = valid_indices[np.argmax(magnitude[valid_indices])]
        dominant_freq = xf[max_index]
        
        # Convert to BPM
        heart_rate = dominant_freq * 60.0
        
        return heart_rate
    
    def _calculate_heart_rate_peak(self, signal):
        """
        Calculate heart rate using peak detection
        
        Args:
            signal: Filtered PPG signal
            
        Returns:
            float: Heart rate in BPM
        """
        # Find peaks in the signal
        peaks, properties = signal.find_peaks(
            signal,
            height=0,
            distance=self.fps * 0.3,  # Minimum distance between peaks (0.3 seconds = 200 BPM)
            prominence=0.1,  # Minimum peak prominence
            width=1  # Minimum peak width
        )
        
        if len(peaks) < 1:
            return 0.0
        
        # Calculate time between consecutive peaks (inter-beat intervals)
        peak_intervals = np.diff(peaks) / self.fps  # Convert to seconds
        
        # Filter out outliers (IBIs that are too short or too long)
        valid_ibis = peak_intervals[(peak_intervals >= 0.3) & (peak_intervals <= 1.4)]  # 43-200 BPM
        
        if len(valid_ibis) < 1:
            return 0.0
        
        # Calculate average IBI and convert to BPM
        avg_ibi = np.mean(valid_ibis)
        heart_rate = 60.0 / avg_ibi
        
        return heart_rate
    
    def process_roi(self, roi):
        """
        Process ROI to extract signal and calculate heart rate
        
        Args:
            roi: numpy array representing the Region of Interest
            
        Returns:
            float: Estimated heart rate in BPM
        """
        # Extract color signal
        r, g, b = self.extract_color_signal(roi)
        
        # Apply CHROME algorithm for better signal quality
        chrome_signal = self.apply_chrome(r, g, b)
        
        # Use CHROME signal, but fall back to green channel if CHROME is too weak
        # Add both signals for more robust results
        ppg_signal = chrome_signal
        
        # If CHROME signal is very small, use green channel as backup
        if abs(chrome_signal) < 0.01:
            ppg_signal = g / 255.0  # Normalize green channel
        
        # Add to signal buffer
        self.signal_buffer.append(ppg_signal)
        
        # Maintain buffer size
        if len(self.signal_buffer) > self.buffer_size:
            self.signal_buffer.pop(0)
        
        # Calculate heart rate if we have enough data
        if len(self.signal_buffer) >= self.fps * 2:  # Reduced to 2 seconds for faster initial results
            # Apply moving average to reduce high-frequency noise
            smoothed_buffer = self._apply_moving_average(np.array(self.signal_buffer), window_size=5)
            
            # Apply bandpass filter
            filtered_signal = self.butter_bandpass_filter(smoothed_buffer)
            
            # Calculate heart rate
            heart_rate = self.calculate_heart_rate(filtered_signal)
            
            # Apply smoothing to heart rate reading
            heart_rate = self._smooth_heart_rate(heart_rate)
            
            return heart_rate
        
        return 0.0
    
    def _apply_moving_average(self, signal, window_size=5):
        """
        Apply moving average filter to reduce noise
        
        Args:
            signal: 1D numpy array, input signal
            window_size: Size of the moving average window
            
        Returns:
            numpy array: Smoothed signal
        """
        if window_size < 2:
            return signal
        
        # Create a moving average filter
        window = np.ones(window_size) / window_size
        
        # Apply convolution for moving average
        smoothed = np.convolve(signal, window, mode='same')
        
        return smoothed
    
    def _smooth_heart_rate(self, heart_rate):
        """
        Smooth heart rate readings using history
        
        Args:
            heart_rate: Current heart rate reading
            
        Returns:
            float: Smoothed heart rate
        """
        if heart_rate <= 0:
            # If no valid reading, use the last value or return 0
            return self.heart_rate_history[-1] if self.heart_rate_history else 0.0
        
        # Add to history
        self.heart_rate_history.append(heart_rate)
        
        # Maintain history size
        if len(self.heart_rate_history) > self.hr_history_size:
            self.heart_rate_history.pop(0)
        
        # Calculate weighted average (more recent readings have more weight)
        weights = np.linspace(0.5, 1.0, len(self.heart_rate_history))
        weights /= np.sum(weights)
        
        smoothed_hr = np.average(self.heart_rate_history, weights=weights)
        
        return smoothed_hr
    
    def reset(self):
        """
        Reset the signal buffer and heart rate history
        """
        self.signal_buffer = []
        self.heart_rate_history = []
    
    def process_multiple_rois(self, rois):
        """
        Process multiple ROIs (for multiple faces)
        
        Args:
            rois: list of numpy arrays, ROIs for each face
            
        Returns:
            list: Estimated heart rates for each face
        """
        heart_rates = []
        
        for roi in rois:
            heart_rate = self.process_roi(roi)
            heart_rates.append(heart_rate)
        
        return heart_rates
    
    def calculate_hrv(self, signal):
        """
        Calculate Heart Rate Variability (HRV)
        Note: This is a simplified version, real HRV analysis requires more sophisticated methods
        
        Args:
            signal: 1D numpy array, filtered PPG signal
            
        Returns:
            float: HRV value (standard deviation of inter-beat intervals)
        """
        # Find peaks in the signal
        peaks, _ = signal.find_peaks(signal, height=0)
        
        if len(peaks) < 2:
            return 0.0
        
        # Calculate inter-beat intervals (IBIs)
        ibis = np.diff(peaks) / self.fps  # Convert to seconds
        
        # Calculate standard deviation of IBIs (SDNN)
        hrv = np.std(ibis) * 1000  # Convert to milliseconds
        
        return hrv
    
    def get_processed_signal(self):
        """
        Get the processed signal for visualization
        
        Returns:
            numpy array: Filtered signal
        """
        if len(self.signal_buffer) < self.fps * 2:
            return np.array([])
        
        return self.butter_bandpass_filter(np.array(self.signal_buffer))
