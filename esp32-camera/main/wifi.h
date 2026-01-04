#ifndef WIFI_H
#define WIFI_H

#include "esp_err.h"

/**
 * @brief Initialize WiFi in STA mode
 * 
 * @return esp_err_t ESP_OK on success
 */
esp_err_t wifi_init_sta(void);

#endif // WIFI_H