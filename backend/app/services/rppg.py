import cv2
import numpy as np
from scipy import signal
from scipy.fft import fft, fftfreq
from scipy.signal import find_peaks, butter, filtfilt, iirnotch
import pywt
import time
import sys
import os

# Add rPPG directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../rPPG'))

# Try to import advanced signal processing modules
try:
    from cdf import CDF
    from asf import ASF
    ADVANCED_SIGNAL_PROCESSING_AVAILABLE = True
except ImportError as e:
    print(f"Advanced signal processing modules import error: {e}")
    ADVANCED_SIGNAL_PROCESSING_AVAILABLE = False

class RPPGService:
    def __init__(self):
        self.signal_buffer = []
        self.buffer_size = 300  # Approximately 15 seconds at 20fps for more stable FFT
        self.low_res_buffer_size = 400  # Larger buffer for low resolution signals
        self.fps = 20.0
        
        # Bandpass filter parameters (0.9-3 Hz corresponds to 54-180 BPM)
        self.lowcut = 0.9
        self.highcut = 3.0
        self.order = 4
        self.low_res_order = 2  # Lower order filter for low resolution signals
        
        # Heart rate smoothing parameters
        self.heart_rate_history = []
        self.hr_history_size = 10  # Smooth over last 10 readings
        self.low_res_hr_history_size = 15  # More smoothing for low resolution signals
        
        # Signal quality parameters
        self.min_signal_quality = 0.15  # Lowered threshold
        self.low_res_min_signal_quality = 0.08  # Lowered threshold for low resolution signals
        
        # CHROME algorithm weights for better signal extraction
        self.chrome_weights = np.array([0.1447, 0.4251, -0.5698])
        
        # POS algorithm parameters
        self.seg_t = 3.2  # Signal segment length in seconds
        self.low_res_seg_t = 4.0  # Longer segment for low resolution signals
        self.l = int(self.fps * self.seg_t)
        self.low_res_l = int(self.fps * self.low_res_seg_t)
        self.B = [int(0.8 // (self.fps / self.l)), int(4 // (self.fps / self.l))]
        self.projection_matrix = np.array([[0, 1, -1], [-2, 1, 1]])
        
        # Wavelet transform parameters
        self.wavelet = 'db4'
        self.level = 3
        self.low_res_level = 2  # Lower level for low resolution signals
        
        # Kalman filter parameters
        self.kalman_enabled = True
        self.kalman_state = None
        self.kalman_process_noise = 1e-3
        self.kalman_measurement_noise = 1e-1
        self.low_res_kalman_measurement_noise = 2e-1  # Higher noise for low resolution
        
        # Multi-ROI fusion parameters
        self.roi_fusion_enabled = True
        self.roi_weights = []
        
        # Ambient light compensation parameters
        self.light_compensation_enabled = True
        self.light_buffer = []
        self.light_buffer_size = 30
        self.light_level = 0.0  # Current light level estimate
        
        # FFT spectrum storage for analysis
        self.fft_spec = []
        
        # Low resolution flag
        self.is_low_res = False
        
        # Adaptive parameter adjustment
        self.adaptive_enabled = True
        self.signal_quality_history = []
        self.quality_history_size = 10
        self.motion_level = 0.0  # Estimated motion level
        self.motion_buffer = []
        self.motion_buffer_size = 10
        
        # Parameter adaptation thresholds
        self.low_quality_threshold = 0.3
        self.high_motion_threshold = 0.5
        self.low_light_threshold = 50.0
        self.high_light_threshold = 200.0
        
        # Adaptive parameters
        self.adaptive_params = {
            'bandpass_order': self.order,
            'wavelet_level': self.level,
            'kalman_measurement_noise': self.kalman_measurement_noise,
            'signal_buffer_size': self.buffer_size,
            'hr_smoothing_window': self.hr_history_size,
            'min_signal_quality': self.min_signal_quality
        }
    
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
    
    def get_pulse(self, mean_rgb):
        """
        Extract pulse signal using POS algorithm
        POS: Pulse Oximetry Signal extraction
        
        Args:
            mean_rgb: numpy array of shape (N, 3) containing mean RGB values
            
        Returns:
            numpy array: Extracted pulse signal
        """
        H = np.zeros(len(mean_rgb))
        
        for t in range(0, (len(mean_rgb) - self.l + 1)):
            # Pre processing steps
            C = mean_rgb[t:t+self.l, :].T
            
            # Apply CDF if available
            if ADVANCED_SIGNAL_PROCESSING_AVAILABLE:
                try:
                    C = CDF(C, self.B)
                except Exception as e:
                    print(f"Error applying CDF: {e}")
            
            # Apply ASF if available
            if ADVANCED_SIGNAL_PROCESSING_AVAILABLE:
                try:
                    C = ASF(C)
                except Exception as e:
                    print(f"Error applying ASF: {e}")
            
            # POS algorithm
            mean_color = np.mean(C, axis=1)
            diag_mean_color = np.diag(mean_color)
            diag_mean_color_inv = np.linalg.inv(diag_mean_color)
            Cn = np.matmul(diag_mean_color_inv, C)
            S = np.matmul(self.projection_matrix, Cn)
            std = np.array([1, np.std(S[0, :])/np.std(S[1, :])])
            P = np.matmul(std, S)
            H[t:t+self.l] = H[t:t+self.l] + (P - np.mean(P))
        
        return H
    
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
        
        # Use appropriate filter order based on adaptive parameters and resolution
        if self.adaptive_enabled:
            order = self.adaptive_params['bandpass_order']
        else:
            order = self.low_res_order if self.is_low_res else self.order
        
        b, a = signal.butter(order, [low, high], btype='band')
        y = signal.filtfilt(b, a, data)
        
        return y
    
    def wavelet_denoise(self, data):
        """
        Apply wavelet denoising to the signal
        
        Args:
            data: 1D numpy array, input signal
            
        Returns:
            numpy array: Denoised signal
        """
        try:
            # Use appropriate wavelet level based on adaptive parameters and resolution
            if self.adaptive_enabled:
                level = self.adaptive_params['wavelet_level']
            else:
                level = self.low_res_level if self.is_low_res else self.level
            
            # Perform wavelet transform
            coeffs = pywt.wavedec(data, self.wavelet, level=level)
            
            # Apply threshold to detail coefficients
            threshold = np.sqrt(2 * np.log(len(data)))
            # Use higher threshold for low resolution signals
            if self.is_low_res:
                threshold *= 1.5
            coeffs[1:] = [pywt.threshold(c, threshold, mode='soft') for c in coeffs[1:]]
            
            # Reconstruct signal
            denoised = pywt.waverec(coeffs, self.wavelet)
            
            # Ensure same length as input
            if len(denoised) != len(data):
                denoised = denoised[:len(data)]
            
            return denoised
        except Exception as e:
            print(f"Error in wavelet denoising: {e}")
            return data
    
    def kalman_filter(self, signal):
        """
        Apply Kalman filter to the signal
        
        Args:
            signal: 1D numpy array, input signal
            
        Returns:
            numpy array: Filtered signal
        """
        if not self.kalman_enabled:
            return signal
        
        try:
            # Initialize Kalman filter if not already initialized
            if self.kalman_state is None:
                # State vector: [signal, signal_derivative]
                self.kalman_state = np.array([signal[0], 0])
                # State covariance matrix
                self.kalman_covariance = np.eye(2)
            
            filtered_signal = np.zeros_like(signal)
            filtered_signal[0] = signal[0]
            
            # Process noise covariance
            Q = np.array([[self.kalman_process_noise, 0], [0, self.kalman_process_noise]])
            
            # Measurement noise covariance based on adaptive parameters and resolution
            if self.adaptive_enabled:
                measurement_noise = self.adaptive_params['kalman_measurement_noise']
            else:
                measurement_noise = self.low_res_kalman_measurement_noise if self.is_low_res else self.kalman_measurement_noise
            
            R = np.array([[measurement_noise]])
            
            for i in range(1, len(signal)):
                # Predict
                # State transition matrix
                F = np.array([[1, 1], [0, 1]])
                # Control matrix
                B = np.array([[0.5], [1]])
                # Control input (acceleration, assumed constant)
                u = 0
                
                # Predict state
                self.kalman_state = np.dot(F, self.kalman_state) + np.dot(B, [u])
                # Predict covariance
                self.kalman_covariance = np.dot(np.dot(F, self.kalman_covariance), F.T) + Q
                
                # Update
                # Measurement matrix
                H = np.array([[1, 0]])
                # Measurement residual
                y = signal[i] - np.dot(H, self.kalman_state)
                # Residual covariance
                S = np.dot(np.dot(H, self.kalman_covariance), H.T) + R
                # Kalman gain
                K = np.dot(np.dot(self.kalman_covariance, H.T), np.linalg.inv(S))
                # Update state
                self.kalman_state = self.kalman_state + np.dot(K, y)
                # Update covariance
                I = np.eye(2)
                self.kalman_covariance = np.dot((I - np.dot(K, H)), self.kalman_covariance)
                
                filtered_signal[i] = self.kalman_state[0]
            
            return filtered_signal
        except Exception as e:
            print(f"Error in Kalman filter: {e}")
            return signal
    
    def ambient_light_compensation(self, roi):
        """
        Compensate for ambient light variations
        
        Args:
            roi: numpy array representing the Region of Interest
            
        Returns:
            numpy array: Light-compensated ROI
        """
        if not self.light_compensation_enabled:
            return roi
        
        try:
            # Calculate average brightness
            brightness = np.mean(roi)
            self.light_buffer.append(brightness)
            
            # Maintain buffer size
            if len(self.light_buffer) > self.light_buffer_size:
                self.light_buffer.pop(0)
            
            # Calculate moving average of brightness
            avg_brightness = np.mean(self.light_buffer)
            
            # Normalize ROI based on average brightness
            if avg_brightness > 0:
                compensation_factor = 128 / avg_brightness  # Target brightness
                compensated_roi = roi * compensation_factor
                compensated_roi = np.clip(compensated_roi, 0, 255).astype(np.uint8)
                return compensated_roi
            return roi
        except Exception as e:
            print(f"Error in ambient light compensation: {e}")
            return roi
    
    def calculate_signal_quality(self, signal):
        """
        Calculate signal quality using multiple metrics
        
        Args:
            signal: Filtered PPG signal
            
        Returns:
            float: Signal quality score (0-1, higher is better)
        """
        try:
            # Signal-to-noise ratio
            mean_val = np.mean(signal)
            std_val = np.std(signal)
            if std_val == 0:
                return 0.0
            snr = std_val / (abs(mean_val) + 1e-6)
            
            # Peak prominence
            peaks, properties = find_peaks(signal, prominence=0.1)
            if len(peaks) < 2:
                return 0.0
            avg_prominence = np.mean(properties['prominences'])
            
            # Frequency content
            yf = fft(signal)
            xf = fftfreq(len(signal), 1 / self.fps)[:len(signal)//2]
            magnitude = 2.0/len(signal) * np.abs(yf[:len(signal)//2])
            valid_indices = np.where((xf >= self.lowcut) & (xf <= self.highcut))[0]
            if len(valid_indices) == 0:
                return 0.0
            power_in_band = np.sum(magnitude[valid_indices])
            total_power = np.sum(magnitude)
            if total_power == 0:
                return 0.0
            frequency_quality = power_in_band / total_power
            
            # Combine metrics
            quality = (snr * 0.4 + avg_prominence * 0.3 + frequency_quality * 0.3)
            quality = min(quality, 1.0)
            quality = max(quality, 0.0)
            
            return quality
        except Exception as e:
            print(f"Error calculating signal quality: {e}")
            return 0.0
    
    def calculate_heart_rate(self, signal):
        """
        Calculate heart rate from filtered signal using advanced techniques
        
        Args:
            signal: 1D numpy array, filtered PPG signal
            
        Returns:
            float: Estimated heart rate in BPM
        """
        n = len(signal)
        if n < 30:  # Need at least 30 points for reliable FFT
            return 0.0
        
        try:
            # Apply wavelet denoising for better signal quality
            denoised_signal = self.wavelet_denoise(signal)
            
            # Apply Kalman filter for smoothness
            filtered_signal = self.kalman_filter(denoised_signal)
            
            # Use FFT for frequency analysis
            heart_rate_fft = self._calculate_heart_rate_fft(filtered_signal)
            
            # Use peak detection as alternative
            heart_rate_peak = self._calculate_heart_rate_peak(filtered_signal)
            
            # Combine results using weighted average
            if heart_rate_fft > 0 and heart_rate_peak > 0:
                # Weight FFT more heavily for better frequency resolution
                heart_rate = (heart_rate_fft * 0.7 + heart_rate_peak * 0.3)
            elif heart_rate_fft > 0:
                heart_rate = heart_rate_fft
            elif heart_rate_peak > 0:
                heart_rate = heart_rate_peak
            else:
                # Fallback to simple method
                heart_rate = self._calculate_heart_rate_simple(filtered_signal)
            
            # Validate heart rate range
            if heart_rate < 40 or heart_rate > 200:
                return 0.0
            
            return heart_rate
        except Exception as e:
            print(f"Error in calculate_heart_rate: {e}")
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
        
        # Store FFT spectrum for analysis
        if len(self.fft_spec) > 100:  # Maintain reasonable size
            self.fft_spec.pop(0)
        self.fft_spec.append({
            'frequencies': xf.tolist(),
            'magnitude': magnitude.tolist(),
            'timestamp': time.time()
        })
        
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
        peaks, properties = find_peaks(
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
    
    def process_roi(self, roi, roi_sequence=None):
        """
        Process ROI to extract signal and calculate heart rate using advanced techniques
        
        Args:
            roi: numpy array representing the Region of Interest
            roi_sequence: list of ROIs from consecutive frames for motion estimation
            
        Returns:
            float: Estimated heart rate in BPM
        """
        # Detect if ROI is from low resolution camera
        if roi is not None and roi.size > 0:
            h, w = roi.shape[:2]
            self.is_low_res = w < 100 or h < 100
        
        # Apply ambient light compensation
        compensated_roi = self.ambient_light_compensation(roi)
        
        # Extract color signal
        r, g, b = self.extract_color_signal(compensated_roi)
        
        # Apply CHROME algorithm for better signal quality
        chrome_signal = self.apply_chrome(r, g, b)
        
        # Use CHROME signal, but fall back to green channel if CHROME is too weak
        ppg_signal = chrome_signal
        
        # If CHROME signal is very small, use green channel as backup
        if abs(chrome_signal) < 0.01:
            ppg_signal = g / 255.0  # Normalize green channel
        
        # Estimate motion level if ROI sequence is provided
        if roi_sequence:
            self.motion_level = self.estimate_motion_level(roi_sequence)
        
        # Add to signal buffer
        self.signal_buffer.append(ppg_signal)
        
        # Get buffer size based on adaptive parameters and resolution
        if self.adaptive_enabled:
            buffer_size = int(self.adaptive_params['signal_buffer_size'])
        else:
            buffer_size = self.low_res_buffer_size if self.is_low_res else self.buffer_size
        
        if len(self.signal_buffer) > buffer_size:
            self.signal_buffer.pop(0)
        
        # Calculate heart rate if we have enough data
        min_buffer_size = self.fps * 3 if self.is_low_res else self.fps * 2  # Reduced buffer size for faster initial detection
        if len(self.signal_buffer) >= min_buffer_size:
            # Apply moving average to reduce high-frequency noise
            window_size = 6 if self.is_low_res else 4  # Smaller window for faster response
            smoothed_buffer = self._apply_moving_average(np.array(self.signal_buffer), window_size=window_size)
            
            # Apply bandpass filter with appropriate order
            filtered_signal = self.butter_bandpass_filter(smoothed_buffer)
            
            # Calculate signal quality
            signal_quality = self.calculate_signal_quality(filtered_signal)
            
            # Update signal quality history
            self.update_signal_quality_history(signal_quality)
            
            # Adjust parameters based on current conditions
            self.adjust_parameters()
            
            # Get appropriate signal quality threshold
            if self.adaptive_enabled:
                min_quality = self.adaptive_params['min_signal_quality']
            else:
                min_quality = self.low_res_min_signal_quality if self.is_low_res else self.min_signal_quality
            
            # Calculate heart rate even if signal quality is low
            # Only calculate heart rate if signal quality is sufficient
            if signal_quality >= min_quality or len(self.signal_buffer) > self.fps * 5:
                # Calculate heart rate
                heart_rate = self.calculate_heart_rate(filtered_signal)
                
                # Apply smoothing to heart rate reading
                heart_rate = self._smooth_heart_rate(heart_rate)
                
                return heart_rate
        
        # If buffer is small but we have some data, try to calculate heart rate anyway
        if len(self.signal_buffer) > self.fps * 1.5:
            # Apply moving average to reduce high-frequency noise
            smoothed_buffer = self._apply_moving_average(np.array(self.signal_buffer), window_size=3)
            
            # Apply bandpass filter with appropriate order
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
        
        # Maintain history size based on adaptive parameters and resolution
        if self.adaptive_enabled:
            hr_history_size = int(self.adaptive_params['hr_smoothing_window'])
        else:
            hr_history_size = self.low_res_hr_history_size if self.is_low_res else self.hr_history_size
        
        if len(self.heart_rate_history) > hr_history_size:
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
    
    def process_multiple_rois(self, rois, multi_face=False):
        """
        Process multiple ROIs (for multiple faces) with fusion
        
        Args:
            rois: list of numpy arrays, ROIs for each face or multiple ROIs for single face
            multi_face: bool, whether the ROIs belong to multiple faces
            
        Returns:
            list: Estimated heart rates for each face
        """
        heart_rates = []
        
        # For multiple faces, process each face separately
        if multi_face:
            for roi in rois:
                # Process each face individually
                heart_rate = self.process_roi(roi)
                heart_rates.append(heart_rate)
        else:
            # For single face with multiple ROIs, apply fusion
            roi_signals = []
            signal_qualities = []
            
            # Process each ROI individually
            for roi in rois:
                # Apply ambient light compensation
                compensated_roi = self.ambient_light_compensation(roi)
                
                # Extract color signal
                r, g, b = self.extract_color_signal(compensated_roi)
                
                # Apply CHROME algorithm
                chrome_signal = self.apply_chrome(r, g, b)
                
                # Store signal
                roi_signals.append(chrome_signal)
                
                # Calculate signal quality
                temp_buffer = [chrome_signal]
                quality = self.calculate_signal_quality(np.array(temp_buffer))
                signal_qualities.append(quality)
            
            # If multiple ROIs, apply fusion
            if len(rois) > 1 and self.roi_fusion_enabled:
                # Calculate weights based on signal quality
                if sum(signal_qualities) > 0:
                    weights = [q / sum(signal_qualities) for q in signal_qualities]
                else:
                    weights = [1.0 / len(rois) for _ in rois]
                
                # Store weights for reference
                self.roi_weights = weights
                
                # Apply signal-level fusion
                fused_signal = self.fuse_roi_signals(roi_signals, weights)
                
                # Process fused signal to get heart rate
                fused_heart_rate = self.process_fused_signal(fused_signal)
                
                # Return fused heart rate for all ROIs (single subject with multiple ROIs)
                heart_rates = [fused_heart_rate] * len(rois)
            else:
                # Process each ROI individually
                for roi in rois:
                    heart_rate = self.process_roi(roi)
                    heart_rates.append(heart_rate)
        
        return heart_rates
    
    def process_multi_face(self, face_rois_list):
        """
        Process multiple faces, each with potentially multiple ROIs
        
        Args:
            face_rois_list: list of lists, where each sublist contains ROIs for a single face
            
        Returns:
            list: Estimated heart rates for each face
        """
        heart_rates = []
        
        # Process each face separately
        for face_rois in face_rois_list:
            if len(face_rois) > 0:
                # Process ROIs for this face (single face with multiple ROIs)
                face_heart_rates = self.process_multiple_rois(face_rois, multi_face=False)
                # Use the first heart rate for this face (they should all be the same due to fusion)
                if face_heart_rates:
                    heart_rates.append(face_heart_rates[0])
                else:
                    heart_rates.append(0.0)
            else:
                heart_rates.append(0.0)
        
        return heart_rates
    
    def fuse_roi_signals(self, roi_signals, weights):
        """
        Fuse signals from multiple ROIs with weighted averaging
        
        Args:
            roi_signals: list of signals from each ROI
            weights: list of weights for each ROI based on signal quality
            
        Returns:
            numpy array: Fused signal
        """
        # Ensure we have signals to fuse
        if not roi_signals or len(roi_signals) == 0:
            return np.array([])
        
        # Convert signals to numpy arrays
        roi_signals_np = []
        max_length = 0
        
        for signal in roi_signals:
            if isinstance(signal, list):
                signal_np = np.array(signal)
            else:
                signal_np = np.array([signal])
            roi_signals_np.append(signal_np)
            max_length = max(max_length, len(signal_np))
        
        # Resize all signals to the same length
        resized_signals = []
        for signal in roi_signals_np:
            if len(signal) < max_length:
                # Pad with zeros
                padded = np.pad(signal, (0, max_length - len(signal)), 'constant')
                resized_signals.append(padded)
            else:
                resized_signals.append(signal[:max_length])
        
        # Apply weighted averaging
        fused = np.zeros(max_length)
        total_weight = sum(weights)
        
        if total_weight > 0:
            for i, signal in enumerate(resized_signals):
                fused += signal * weights[i]
            fused /= total_weight
        
        return fused
    
    def process_fused_signal(self, fused_signal):
        """
        Process fused signal to calculate heart rate
        
        Args:
            fused_signal: numpy array, fused signal from multiple ROIs
            
        Returns:
            float: Estimated heart rate in BPM
        """
        if len(fused_signal) < self.fps * 2:  # Need at least 2 seconds of data
            return 0.0
        
        try:
            # Apply moving average
            smoothed_signal = self._apply_moving_average(fused_signal, window_size=6)
            
            # Apply bandpass filter
            filtered_signal = self.butter_bandpass_filter(smoothed_signal)
            
            # Calculate signal quality
            signal_quality = self.calculate_signal_quality(filtered_signal)
            
            # Only calculate heart rate if signal quality is sufficient
            if signal_quality >= self.min_signal_quality:
                # Calculate heart rate
                heart_rate = self.calculate_heart_rate(filtered_signal)
                
                # Apply smoothing to heart rate reading
                heart_rate = self._smooth_heart_rate(heart_rate)
                
                return heart_rate
        except Exception as e:
            print(f"Error processing fused signal: {e}")
        
        return 0.0
    
    def extract_multiple_rois(self, face_frame):
        """
        Extract multiple ROIs from a single face frame
        
        Args:
            face_frame: numpy array representing the face region
            
        Returns:
            list: Multiple ROIs from different facial regions
        """
        rois = []
        h, w = face_frame.shape[:2]
        
        # Extract forehead ROI
        forehead_top = 0
        forehead_bottom = int(h * 0.3)
        forehead_left = int(w * 0.2)
        forehead_right = int(w * 0.8)
        forehead_roi = face_frame[forehead_top:forehead_bottom, forehead_left:forehead_right]
        rois.append(forehead_roi)
        
        # Extract left cheek ROI
        left_cheek_top = int(h * 0.3)
        left_cheek_bottom = int(h * 0.7)
        left_cheek_left = 0
        left_cheek_right = int(w * 0.4)
        left_cheek_roi = face_frame[left_cheek_top:left_cheek_bottom, left_cheek_left:left_cheek_right]
        rois.append(left_cheek_roi)
        
        # Extract right cheek ROI
        right_cheek_top = int(h * 0.3)
        right_cheek_bottom = int(h * 0.7)
        right_cheek_left = int(w * 0.6)
        right_cheek_right = w
        right_cheek_roi = face_frame[right_cheek_top:right_cheek_bottom, right_cheek_left:right_cheek_right]
        rois.append(right_cheek_roi)
        
        # Extract nose ROI
        nose_top = int(h * 0.3)
        nose_bottom = int(h * 0.6)
        nose_left = int(w * 0.4)
        nose_right = int(w * 0.6)
        nose_roi = face_frame[nose_top:nose_bottom, nose_left:nose_right]
        rois.append(nose_roi)
        
        return rois
    
    def estimate_motion_level(self, roi_sequence):
        """
        Estimate motion level based on ROI sequence
        
        Args:
            roi_sequence: list of ROIs from consecutive frames
            
        Returns:
            float: Motion level estimate (0-1, higher is more motion)
        """
        if len(roi_sequence) < 2:
            return 0.0
        
        try:
            motion_values = []
            
            for i in range(1, len(roi_sequence)):
                # Calculate difference between consecutive ROIs
                prev_roi = roi_sequence[i-1]
                curr_roi = roi_sequence[i]
                
                if prev_roi.size == 0 or curr_roi.size == 0:
                    continue
                
                # Resize to same size
                min_h = min(prev_roi.shape[0], curr_roi.shape[0])
                min_w = min(prev_roi.shape[1], curr_roi.shape[1])
                
                prev_roi_resized = cv2.resize(prev_roi, (min_w, min_h))
                curr_roi_resized = cv2.resize(curr_roi, (min_w, min_h))
                
                # Calculate absolute difference
                diff = cv2.absdiff(prev_roi_resized, curr_roi_resized)
                mean_diff = np.mean(diff)
                
                # Normalize to 0-1
                motion = min(1.0, mean_diff / 255.0)
                motion_values.append(motion)
            
            if motion_values:
                motion_level = np.mean(motion_values)
                # Update motion buffer
                self.motion_buffer.append(motion_level)
                if len(self.motion_buffer) > self.motion_buffer_size:
                    self.motion_buffer.pop(0)
                # Return smoothed motion level
                return np.mean(self.motion_buffer)
            return 0.0
        except Exception as e:
            print(f"Error estimating motion level: {e}")
            return 0.0
    
    def update_signal_quality_history(self, quality):
        """
        Update signal quality history for adaptive parameter adjustment
        
        Args:
            quality: float, current signal quality
        """
        self.signal_quality_history.append(quality)
        if len(self.signal_quality_history) > self.quality_history_size:
            self.signal_quality_history.pop(0)
    
    def adjust_parameters(self):
        """
        Adjust system parameters based on current conditions
        """
        if not self.adaptive_enabled:
            return
        
        try:
            # Calculate average signal quality
            avg_quality = np.mean(self.signal_quality_history) if self.signal_quality_history else 1.0
            
            # Get current motion level
            current_motion = np.mean(self.motion_buffer) if self.motion_buffer else 0.0
            
            # Get current light level
            current_light = self.light_level
            
            # Adjust parameters based on conditions
            
            # 1. Adjust based on signal quality
            if avg_quality < self.low_quality_threshold:
                # Lower signal quality: increase smoothing and buffer size
                self.adaptive_params['signal_buffer_size'] = min(400, self.buffer_size * 1.5)
                self.adaptive_params['hr_smoothing_window'] = min(15, self.hr_history_size * 1.5)
                self.adaptive_params['min_signal_quality'] = max(0.1, self.min_signal_quality * 0.8)
                self.adaptive_params['kalman_measurement_noise'] = min(0.5, self.kalman_measurement_noise * 1.2)
            else:
                # Restore default parameters
                self.adaptive_params['signal_buffer_size'] = self.buffer_size
                self.adaptive_params['hr_smoothing_window'] = self.hr_history_size
                self.adaptive_params['min_signal_quality'] = self.min_signal_quality
                self.adaptive_params['kalman_measurement_noise'] = self.kalman_measurement_noise
            
            # 2. Adjust based on motion level
            if current_motion > self.high_motion_threshold:
                # High motion: increase smoothing and reduce filter order
                self.adaptive_params['hr_smoothing_window'] = min(20, self.hr_history_size * 2)
                self.adaptive_params['bandpass_order'] = max(2, self.order - 1)
                self.adaptive_params['wavelet_level'] = max(2, self.level - 1)
            else:
                # Restore default parameters
                self.adaptive_params['hr_smoothing_window'] = self.hr_history_size
                self.adaptive_params['bandpass_order'] = self.order
                self.adaptive_params['wavelet_level'] = self.level
            
            # 3. Adjust based on light level
            if current_light < self.low_light_threshold or current_light > self.high_light_threshold:
                # Extreme light conditions: increase buffer size and smoothing
                self.adaptive_params['signal_buffer_size'] = min(400, self.buffer_size * 1.3)
                self.adaptive_params['hr_smoothing_window'] = min(15, self.hr_history_size * 1.3)
            
            # Update light level based on recent light buffer
            if self.light_buffer:
                self.light_level = np.mean(self.light_buffer)
                
        except Exception as e:
            print(f"Error adjusting parameters: {e}")
    
    def calculate_hrv(self, signal):
        """
        Calculate comprehensive Heart Rate Variability (HRV) metrics
        
        Args:
            signal: 1D numpy array, filtered PPG signal
            
        Returns:
            dict: HRV metrics including SDNN, RMSSD, NN50, pNN50, etc.
        """

        # Find peaks in the signal
        peaks, properties = find_peaks(signal, height=0, distance=self.fps * 0.3)
        
        if len(peaks) < 5:  # Need at least 5 peaks for meaningful HRV analysis
            return {
                'sdnn': 0.0,      # Standard deviation of NN intervals
                'rmssd': 0.0,     # Root mean square of successive differences
                'nn50': 0,        # Number of NN intervals differing by >50ms
                'pnn50': 0.0,     # Percentage of NN50 intervals
                'mean_ibi': 0.0,   # Mean of NN intervals
                'std_ibi': 0.0,    # Standard deviation of NN intervals
                'ibi_count': 0     # Number of NN intervals
            }
        
        # Calculate inter-beat intervals (IBIs) in milliseconds
        ibis = np.diff(peaks) / self.fps * 1000  # Convert to milliseconds
        
        # Calculate HRV metrics
        sdnn = np.std(ibis)  # Standard deviation of NN intervals
        
        # Root mean square of successive differences
        successive_diff = np.diff(ibis)
        rmssd = np.sqrt(np.mean(successive_diff ** 2))
        
        # NN50 and pNN50
        nn50 = np.sum(np.abs(successive_diff) > 50)
        pnn50 = (nn50 / len(successive_diff)) * 100 if len(successive_diff) > 0 else 0
        
        # Mean and standard deviation of IBIs
        mean_ibi = np.mean(ibis)
        std_ibi = np.std(ibis)
        
        return {
            'sdnn': sdnn,
            'rmssd': rmssd,
            'nn50': nn50,
            'pnn50': pnn50,
            'mean_ibi': mean_ibi,
            'std_ibi': std_ibi,
            'ibi_count': len(ibis)
        }
    
    def get_processed_signal(self):
        """
        Get the processed signal for visualization
        
        Returns:
            numpy array: Filtered signal
        """
        if len(self.signal_buffer) < self.fps * 2:
            return np.array([])
        
        return self.butter_bandpass_filter(np.array(self.signal_buffer))
