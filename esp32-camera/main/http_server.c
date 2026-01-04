#include <esp_log.h>
#include <esp_http_server.h>
#include <string.h>
#include <esp_camera.h>

#include "camera.h"
#include "http_server.h"

static const char *TAG = "http_server";

/* Default HTTP response headers */
static const char *CONTENT_TYPE_JPEG = "image/jpeg";
static const char *CONTENT_TYPE_TEXT_PLAIN = "text/plain";
static const char *CONTENT_TYPE_HTML = "text/html";
static const char *CONTENT_TYPE_MJPEG = "multipart/x-mixed-replace; boundary=frame";
static const char *CORS_HEADERS = "Access-Control-Allow-Origin: *\r\n";

/* Simple HTML response for root path */
static const char* ROOT_HTML = "<!DOCTYPE html>\n" \
                               "<html>\n" \
                               "<head>\n" \
                               "    <title>ESP32-S3-EYE Camera</title>\n" \
                               "</head>\n" \
                               "<body>\n" \
                               "    <h1>ESP32-S3-EYE Camera Stream</h1>\n" \
                               "    <img src=\"/stream\" width=640 height=480 />\n" \
                               "    <p>Stream URL: <a href=\"/stream\">/stream</a></p>\n" \
                               "</body>\n" \
                               "</html>\n";

/* HTTP request handler for root path */
static esp_err_t http_handler_root(httpd_req_t *req)
{
    httpd_resp_set_type(req, CONTENT_TYPE_HTML);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_send(req, ROOT_HTML, strlen(ROOT_HTML));
    return ESP_OK;
}

/* HTTP request handler for MJPEG stream */
static esp_err_t http_handler_stream(httpd_req_t *req)
{
    ESP_LOGI(TAG, "Client connected for stream");

    /* Set HTTP response type and headers */
    httpd_resp_set_type(req, CONTENT_TYPE_MJPEG);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    httpd_resp_set_hdr(req, "Cache-Control", "no-cache");
    httpd_resp_set_hdr(req, "Connection", "close");
    
    /* Disable chunked encoding by setting content length to a large value */
    /* This forces esp_http_server to use Content-Length instead of Transfer-Encoding: chunked */
    httpd_resp_set_hdr(req, "Content-Length", "10000000");

    /* Buffer for the frame data */
    camera_fb_t *frame = NULL;
    size_t frame_len = 0;

    /* Loop to send frames */
    while (1) {
        /* Capture a frame */
        esp_err_t ret = camera_capture_frame(&frame, &frame_len);
        if (ret != ESP_OK) {
            ESP_LOGE(TAG, "Failed to capture frame");
            break;
        }

        /* Send the MJPEG frame boundary */
        const char* boundary = "--frame\r\n";
        if (httpd_resp_send_chunk(req, boundary, strlen(boundary)) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to send boundary");
            camera_return_frame(frame);
            break;
        }

        /* Send the content type header */
        char content_type[50];
        int ct_len = sprintf(content_type, "Content-Type: %s\r\n", CONTENT_TYPE_JPEG);
        if (httpd_resp_send_chunk(req, content_type, ct_len) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to send content type");
            camera_return_frame(frame);
            break;
        }

        /* Send the content length header */
        char content_length[50];
        int cl_len = sprintf(content_length, "Content-Length: %zu\r\n\r\n", frame_len);
        if (httpd_resp_send_chunk(req, content_length, cl_len) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to send content length");
            camera_return_frame(frame);
            break;
        }

        /* Send the JPEG data */
        if (httpd_resp_send_chunk(req, (const char *)frame->buf, frame_len) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to send frame data");
            camera_return_frame(frame);
            break;
        }

        /* Send the end of frame */
        const char* end_frame = "\r\n";
        if (httpd_resp_send_chunk(req, end_frame, strlen(end_frame)) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to send end of frame");
            camera_return_frame(frame);
            break;
        }

        /* Return the frame to the camera driver */
        camera_return_frame(frame);

        /* Small delay to control frame rate */
        vTaskDelay(pdMS_TO_TICKS(33)); // ~30fps
    }

    ESP_LOGI(TAG, "Client disconnected from stream");
    return ESP_OK;
}

/* HTTP server configuration */
static httpd_uri_t uri_root = {
    .uri = "/",
    .method = HTTP_GET,
    .handler = http_handler_root,
    .user_ctx = NULL
};

static httpd_uri_t uri_stream = {
    .uri = "/stream",
    .method = HTTP_GET,
    .handler = http_handler_stream,
    .user_ctx = NULL
};

esp_err_t http_server_start(void)
{
    static httpd_handle_t server = NULL;

    /* Start the HTTP server */
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 80;
    config.uri_match_fn = httpd_uri_match_wildcard;

    /* Start the server */
    if (httpd_start(&server, &config) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start HTTP server");
        return ESP_FAIL;
    }

    /* Register the root URI handler */
    httpd_register_uri_handler(server, &uri_root);

    /* Register the stream URI handler */
    httpd_register_uri_handler(server, &uri_stream);

    ESP_LOGI(TAG, "HTTP server started on port %d", config.server_port);
    return ESP_OK;
}