#ifndef HTTP_SERVER_H
#define HTTP_SERVER_H

#include "esp_err.h"

/**
 * @brief Start the HTTP server
 * 
 * @return esp_err_t ESP_OK on success
 */
esp_err_t http_server_start(void);

#endif // HTTP_SERVER_H