#include <esp_camera.h>
#include <esp_log.h>
#include "camera.h"

static const char *TAG = "camera";

// ESP32-S3-WROOM-1 external camera pins configuration (for OV2640)
#define CAM_PIN_PWDN    -1  // Power down is not used
#define CAM_PIN_RESET   -1  // Reset pin is not used
#define CAM_PIN_XCLK    15
#define CAM_PIN_SIOD    4
#define CAM_PIN_SIOC    5

#define CAM_PIN_D7      39
#define CAM_PIN_D6      40
#define CAM_PIN_D5      41
#define CAM_PIN_D4      42
#define CAM_PIN_D3      14
#define CAM_PIN_D2      13
#define CAM_PIN_D1      12
#define CAM_PIN_D0      11
#define CAM_PIN_VSYNC   21
#define CAM_PIN_HREF    38
#define CAM_PIN_PCLK    10

static camera_config_t camera_config = {
    .pin_pwdn = CAM_PIN_PWDN,
    .pin_reset = CAM_PIN_RESET,
    .pin_xclk = CAM_PIN_XCLK,
    .pin_sccb_sda = CAM_PIN_SIOD,
    .pin_sccb_scl = CAM_PIN_SIOC,

    .pin_d7 = CAM_PIN_D7,
    .pin_d6 = CAM_PIN_D6,
    .pin_d5 = CAM_PIN_D5,
    .pin_d4 = CAM_PIN_D4,
    .pin_d3 = CAM_PIN_D3,
    .pin_d2 = CAM_PIN_D2,
    .pin_d1 = CAM_PIN_D1,
    .pin_d0 = CAM_PIN_D0,
    .pin_vsync = CAM_PIN_VSYNC,
    .pin_href = CAM_PIN_HREF,
    .pin_pclk = CAM_PIN_PCLK,

    // XCLK 20MHz for ESP32-S3-WROOM-1 OV2640
    .xclk_freq_hz = 20000000,
    .ledc_timer = LEDC_TIMER_0,
    .ledc_channel = LEDC_CHANNEL_0,

    .pixel_format = PIXFORMAT_JPEG,// Set to JPEG format for faster processing
    .frame_size = FRAMESIZE_VGA,    // 640x480 resolution (OV2640 can handle this)
    .jpeg_quality = 12,             // 0-63, lower is higher quality (12 = high quality)
    .fb_count = 2,                  // Number of frame buffers (2 for better performance)
    .grab_mode = CAMERA_GRAB_WHEN_EMPTY,
    .fb_location = CAMERA_FB_IN_PSRAM, // Use PSRAM for frame buffer
    .sccb_i2c_port = I2C_NUM_0,
};

esp_err_t camera_init(void)
{
    // Initialize the camera
    esp_err_t err = esp_camera_init(&camera_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Camera init failed with error 0x%x", err);
        return err;
    }

    // Get camera sensor
    sensor_t *sensor = esp_camera_sensor_get();
    if (!sensor) {
        ESP_LOGE(TAG, "Failed to get camera sensor");
        return ESP_FAIL;
    }

    // Set sensor parameters for better performance (OV2640 specific)
    sensor->set_pixformat(sensor, PIXFORMAT_JPEG); // Explicitly set JPEG format
    sensor->set_framesize(sensor, FRAMESIZE_VGA); // Match config frame size (640x480)
    sensor->set_quality(sensor, 12); // Match config JPEG quality (high quality)
    sensor->set_vflip(sensor, 1); // Flip vertically (common for OV2640)
    sensor->set_hmirror(sensor, 1); // Mirror horizontally (common for OV2640)
    sensor->set_saturation(sensor, 0); // Normal saturation
    sensor->set_brightness(sensor, 0); // Normal brightness
    sensor->set_contrast(sensor, 0); // Normal contrast

    // Add delay to ensure camera is stable
    vTaskDelay(pdMS_TO_TICKS(1000)); // 1 second delay for OV2640 initialization

    ESP_LOGI(TAG, "Camera initialized successfully");
    return ESP_OK;
}

esp_err_t camera_capture_frame(camera_fb_t **frame, size_t *frame_len)
{
    if (!frame || !frame_len) {
        return ESP_ERR_INVALID_ARG;
    }

    // Maximum number of retries
    int max_retries = 5;
    int retry_count = 0;

    while (retry_count < max_retries) {
        // Acquire a frame
        camera_fb_t *fb = esp_camera_fb_get();
        if (!fb) {
            ESP_LOGE(TAG, "Failed to acquire frame");
            retry_count++;
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }

        // Check if the frame is a valid JPEG (has SOI marker 0xFF 0xD8)
        if (fb->len >= 2 && fb->buf[0] == 0xFF && fb->buf[1] == 0xD8) {
            // Valid JPEG frame
            *frame = fb;
            *frame_len = fb->len;
            return ESP_OK;
        } else {
            // Invalid JPEG frame, return it to the driver
            esp_camera_fb_return(fb);
            ESP_LOGE(TAG, "Invalid JPEG frame (missing SOI marker), retry %d/%d", retry_count + 1, max_retries);
            retry_count++;
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }

    ESP_LOGE(TAG, "Failed to acquire valid JPEG frame after %d retries", max_retries);
    return ESP_ERR_TIMEOUT;
}

esp_err_t camera_return_frame(camera_fb_t *frame)
{
    if (!frame) {
        return ESP_ERR_INVALID_ARG;
    }

    // Return the frame buffer to the camera driver
    esp_camera_fb_return(frame);
    return ESP_OK;
}