from flask import Flask, Response, jsonify
from flask_cors import CORS
import cv2
import threading
import time
import logging
import atexit

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Global variables
camera = None
camera_thread = None
is_streaming = False
frame = None
frame_lock = threading.Lock()
stream_lock = threading.Lock()

def init_camera():
    """Initialize the camera"""
    global camera
    try:
        # Release camera if it's already initialized
        release_camera()
        
        logger.debug("Attempting to initialize camera...")
        
        # Try different camera indices and backends
        camera_indices = [0, 2, -1]  # Try main camera, USB camera, and auto-detect
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]  # Try V4L2 first, then any backend
        
        for idx in camera_indices:
            for backend in backends:
                try:
                    logger.debug(f"Trying camera index {idx} with backend {backend}")
                    camera = cv2.VideoCapture(idx, backend)
                    if camera.isOpened():
                        # Set camera properties
                        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        camera.set(cv2.CAP_PROP_FPS, 30)
                        camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        
                        # Test capture
                        ret, test_frame = camera.read()
                        if ret and test_frame is not None:
                            logger.info(f"Camera initialized successfully with index {idx} and backend {backend}")
                            return True
                        
                        camera.release()
                except Exception as e:
                    logger.warning(f"Failed with camera index {idx} and backend {backend}: {e}")
                    continue
        
        logger.error("Failed to initialize camera with any configuration")
        return False
    except Exception as e:
        logger.error(f"Error initializing camera: {e}", exc_info=True)
        return False

def release_camera():
    """Release the camera resources"""
    global camera, is_streaming
    with stream_lock:
        is_streaming = False
        if camera is not None:
            camera.release()
            camera = None
            logger.info("Camera released")

def camera_stream():
    """Function to capture frames from the camera"""
    global camera, is_streaming, frame
    logger.info("Starting camera stream thread")
    frame_count = 0
    last_log = time.time()
    
    while is_streaming:
        try:
            if camera is None or not camera.isOpened():
                logger.error("Camera is not available")
                time.sleep(1)
                continue
                
            ret, current_frame = camera.read()
            if ret and current_frame is not None:
                frame_count += 1
                with frame_lock:
                    frame = current_frame.copy()
                
                # Log FPS every 5 seconds
                current_time = time.time()
                if current_time - last_log >= 5:
                    fps = frame_count / (current_time - last_log)
                    logger.info(f"Streaming at {fps:.2f} FPS")
                    frame_count = 0
                    last_log = current_time
            else:
                logger.warning("Failed to capture frame")
                time.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in camera stream: {e}", exc_info=True)
            time.sleep(0.1)

def generate_frames():
    """Generator function to yield frames for streaming"""
    global frame
    logger.info("Starting frame generation")
    
    while True:
        with frame_lock:
            if frame is not None:
                try:
                    # Convert frame to JPEG with quality setting
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                    ret, buffer = cv2.imencode('.jpg', frame, encode_param)
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                        continue
                except Exception as e:
                    logger.error(f"Error encoding frame: {e}", exc_info=True)
            time.sleep(0.1)

@app.route('/')
def index():
    """Home page"""
    return "Camera Streaming Server"

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})

@app.route('/stream-status')
def stream_status():
    """Check if the stream is active and working"""
    global camera, frame
    with frame_lock:
        if camera is not None and camera.isOpened() and frame is not None:
            return jsonify({"status": "streaming"})
    return jsonify({"status": "not streaming"}), 503

@app.route('/start-stream', methods=['POST'])
def start_stream():
    """Start the camera stream"""
    global camera, camera_thread, is_streaming
    
    logger.info("Received start stream request")
    
    try:
        with stream_lock:
            if is_streaming:
                logger.info("Camera already streaming")
                return jsonify({"status": "success", "message": "Camera already streaming"})
            
            logger.debug("Initializing camera...")
            if not init_camera():
                logger.error("Failed to initialize camera")
                return jsonify({"status": "error", "message": "Failed to initialize camera"}), 500
            
            logger.debug("Starting camera thread...")
            is_streaming = True
            camera_thread = threading.Thread(target=camera_stream)
            camera_thread.daemon = True
            camera_thread.start()
            
            logger.info("Camera stream started successfully")
            return jsonify({"status": "success", "message": "Camera stream started"})
    except Exception as e:
        logger.error(f"Error starting stream: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop-stream', methods=['POST'])
def stop_stream():
    """Stop the camera stream"""
    logger.info("Received stop stream request")
    try:
        release_camera()
        return jsonify({"status": "success", "message": "Camera stream stopped"})
    except Exception as e:
        logger.error(f"Error stopping stream: {e}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream')
def video_feed():
    """Video streaming route"""
    logger.info("Stream endpoint accessed")
    if not is_streaming:
        logger.warning("Stream accessed while not streaming")
        return "Stream not active", 503
    return Response(generate_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

def cleanup():
    """Cleanup function to be called on server shutdown"""
    release_camera()

# Register cleanup function
atexit.register(cleanup)

if __name__ == '__main__':
    try:
        logger.info("Starting Flask server...")
        app.run(host='0.0.0.0', port=5000, threaded=True)
    finally:
        release_camera()
