#ifndef CAMERA_H
#define CAMERA_H

#include "esp_err.h"
#include "esp_camera.h"

/**
 * @brief Initialize camera
 * 
 * @return esp_err_t ESP_OK on success
 */
esp_err_t camera_init(void);

/**
 * @brief Capture a frame from the camera
 * 
 * @param[out] frame Pointer to store the frame buffer
 * @param[out] frame_len Length of the frame in bytes
 * @return esp_err_t ESP_OK on success
 */
esp_err_t camera_capture_frame(camera_fb_t **frame, size_t *frame_len);

/**
 * @brief Return a frame to the camera driver
 * 
 * @param frame Frame buffer to return
 * @return esp_err_t ESP_OK on success
 */
esp_err_t camera_return_frame(camera_fb_t *frame);

#endif // CAMERA_H