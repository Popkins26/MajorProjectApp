from flask import Flask, jsonify, Response
import cv2
import time
import os
import firebase_admin
from firebase_admin import credentials, storage
import threading

# Firebase Initialization
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'project-app-8f1c2.appspot.com'
})
bucket = storage.bucket()

app = Flask(__name__)

camera = None
is_streaming = False
frame = None
frame_lock = threading.Lock()

def camera_stream():
    global camera, is_streaming, frame
    while is_streaming:
        ret, current_frame = camera.read()
        if ret:
            with frame_lock:
                frame = current_frame.copy()

@app.route('/start-stream', methods=['POST'])
def start_stream():
    global camera, is_streaming
    if is_streaming:
        return jsonify({'status': 'success', 'message': 'Already streaming'})
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        return jsonify({'status': 'error', 'message': 'Camera not available'}), 500
    is_streaming = True
    threading.Thread(target=camera_stream, daemon=True).start()
    return jsonify({'status': 'success', 'message': 'Camera stream started'})

@app.route('/stop-stream', methods=['POST'])
def stop_stream():
    global camera, is_streaming
    is_streaming = False
    if camera:
        camera.release()
        camera = None
    return jsonify({'status': 'success', 'message': 'Camera stream stopped'})

@app.route('/stream')
def video_feed():
    def generate_frames():
        global frame
        while True:
            with frame_lock:
                if frame is not None:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    if ret:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/snapshot', methods=['POST'])
def take_snapshot():
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        return jsonify({'error': 'Camera not available'}), 500

    ret, img = camera.read()
    camera.release()
    if not ret:
        return jsonify({'error': 'Failed to capture image'}), 500

    filename = f"snapshot_{int(time.time())}.jpg"
    cv2.imwrite(filename, img)

    # Upload to Firebase Storage
    blob = bucket.blob(f"camera_snapshots/{filename}")
    blob.upload_from_filename(filename)
    os.remove(filename)
    url = blob.generate_signed_url(expiration=3600)  # 1 hour signed URL

    return jsonify({'url': url}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)