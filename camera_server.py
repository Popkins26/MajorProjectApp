from flask import Flask, Response, jsonify
import cv2
import threading
import time
import logging
import os
from datetime import datetime
import sys
# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global variables
camera = None
camera_thread = None
is_streaming = False
frame = None
frame_lock = threading.Lock()

def init_camera():
    """Initialize the USB camera"""
    global camera
    try:
        # Try to open the USB camera (0 is usually the default camera)
        camera = cv2.VideoCapture(0)
        if not camera.isOpened():
            logger.error("Failed to open camera")
            return False
        
        # Set camera properties
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 30)
        
        logger.info("USB Camera initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing camera: {e}")
        return False

def release_camera():
    """Release the camera resources"""
    global camera, is_streaming
    is_streaming = False
    if camera is not None:
        camera.release()
        camera = None

def camera_stream():
    """Function to capture frames from the camera"""
    global camera, is_streaming, frame
    
    while is_streaming:
        try:
            ret, current_frame = camera.read()
            if ret:
                with frame_lock:
                    frame = current_frame.copy()
            else:
                logger.warning("Failed to capture frame")
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in camera stream: {e}")
            time.sleep(0.1)

def generate_frames():
    """Generator function to yield frames for streaming"""
    global frame
    
    while True:
        with frame_lock:
            if frame is not None:
                # Convert frame to JPEG
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    # Yield the frame in MJPEG format
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            else:
                # If no frame is available, yield an empty frame
                time.sleep(0.1)

@app.route('/')
def index():
    """Home page"""
    return "USB Camera Streaming Server"

@app.route('/start-stream', methods=['POST'])
def start_stream():
    """Start the camera stream"""
    global camera, camera_thread, is_streaming
    
    try:
        if is_streaming:
            return jsonify({"status": "success", "message": "Camera already streaming"})
        
        if not init_camera():
            return jsonify({"status": "error", "message": "Failed to initialize camera"}), 500
        
        is_streaming = True
        camera_thread = threading.Thread(target=camera_stream)
        camera_thread.daemon = True
        camera_thread.start()
        
        logger.info("Camera stream started")
        return jsonify({"status": "success", "message": "Camera stream started"})
    except Exception as e:
        logger.error(f"Error starting stream: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop-stream', methods=['POST'])
def stop_stream():
    """Stop the camera stream"""
    global is_streaming
    
    try:
        if not is_streaming:
            return jsonify({"status": "success", "message": "Camera already stopped"})
        
        release_camera()
        return jsonify({"status": "success", "message": "Camera stream stopped"})
    except Exception as e:
        logger.error(f"Error stopping stream: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream')
def video_feed():
    """Video streaming route. Returns MJPEG stream."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def record_video_and_upload():
    """Record a 10-second video and upload to Firebase."""
    print("Starting 10-second video recording...")
    if not init_camera():
        print("Failed to initialize camera for recording.")
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"video_{timestamp}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(filename, fourcc, 30.0, (640, 480))
    start_time = time.time()
    while (time.time() - start_time) < 10:
        ret, frame = camera.read()
        if ret:
            out.write(frame)
    out.release()
    release_camera()
    print(f"Recording complete: {filename}")
    # TODO: Add your upload logic here
    # upload_video_to_firebase(filename)
    if os.path.exists(filename):
        os.remove(filename)
    print("Done.")

if __name__ == '__main__':
    if '--record' in sys.argv:
        record_video_and_upload()
    else:
        app.run(host='0.0.0.0', port=5000, threaded=True) 