# Camera Streaming Setup

This document provides instructions on how to set up and run the camera streaming functionality for the Care Taker Bot application.

## Prerequisites

1. Python 3.7 or higher
2. OpenCV
3. Flask
4. MJPG Streamer (for direct streaming)

## Setup Instructions

### 1. Install Required Python Packages

```bash
pip install -r requirements.txt
```

### 2. Install MJPG Streamer (Optional)

If you want to use MJPG Streamer for direct streaming:

1. Download MJPG Streamer from [https://sourceforge.net/projects/mjpg-streamer/](https://sourceforge.net/projects/mjpg-streamer/)
2. Extract to `C:\Program Files\mjpg-streamer\`
3. Run `start_mjpg_streamer.bat` to start the streamer

### 3. Start the Flask Server

```bash
python camera_server.py
```

This will start the Flask server on port 5000.

## Using the Camera Stream in the App

1. Make sure the Flask server is running
2. Open the Emergency Page in the app
3. Click the "Start Camera Stream" button
4. The camera stream should appear in the app

## Troubleshooting

### Common Issues

1. **Camera not found**: Make sure your camera is properly connected and recognized by your system.
2. **Stream not loading**: Check that both the Flask server and MJPG Streamer (if using) are running.
3. **Network issues**: Ensure your device is on the same network as the server.

### Debugging

- Check the Flask server logs for any errors
- Make sure the IP address in the app matches your server's IP address
- Try accessing the stream URL directly in a browser: `http://<server-ip>:8080/stream`

## API Endpoints

- `POST /start-stream`: Start the camera stream
- `POST /stop-stream`: Stop the camera stream
- `GET /stream`: Get the video feed (MJPEG stream) 