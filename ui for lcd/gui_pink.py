import tkinter as tk
from tkinter import messagebox, simpledialog
import datetime
import os
import cv2
import sounddevice as sd
import soundfile as sf
from scipy.io.wavfile import write
import time
import threading
import numpy as np
import firebase_admin
from firebase_admin import credentials, storage, firestore
import logging
from datetime import datetime, timedelta
from tkinter import ttk
import tempfile
from urllib.request import urlopen
from PIL import Image, ImageTk
import io
import requests
import io
import subprocess
from pydub import AudioSegment
import wave
import tkcalendar
from tkcalendar import DateEntry
import pygame  # For audio playback

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set ffmpeg paths for pydub - Raspberry Pi configuration
AudioSegment.converter = "/usr/bin/ffmpeg"
AudioSegment.ffmpeg = "/usr/bin/ffmpeg"
AudioSegment.ffprobe = "/usr/bin/ffprobe"

# Set default audio device
try:
    # Find Realtek speakers
    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if 'Realtek' in device['name'] and device['max_output_channels'] > 0:
            sd.default.device = i
            logging.debug(f"Set default audio device to: {device['name']}")
            break
except Exception as e:
    logging.error(f"Error setting default audio device: {e}")

# Firebase Initialization
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'project-app-8f1c2.appspot.com'
})
bucket = storage.bucket()
db = firestore.client()

# Global variables
user_profile_pic_url = None
user_name = "User"  # Default name
current_task = None
task_sent_time = None
task_due_time = None
temp_files = []  # List to store temporary files
current_audio_position = 0  # Track current audio position for resume functionality
snooze_timer = None  # Timer for snooze functionality

# Audio playback variables
is_playing = False
playback_thread = None
audio_data = None
sample_rate = 44100
playback_position = 0
playback_duration = 0
playback_stop_event = threading.Event()

# Recording state
is_recording = False
recording_thread = None
recording_buffer = []

# Camera server variables
camera_server = None
camera = None
camera_thread = None
is_streaming = False
frame = None
frame_lock = threading.Lock()

# Constants for UI consistency
STANDARD_FONT = ("DejaVu Sans", 12)  # Using DejaVu Sans which is better supported on Raspberry Pi
TITLE_FONT = ("DejaVu Sans", 24, "bold")
BUTTON_FONT = ("DejaVu Sans", 14)
STANDARD_BG = "#EDF1E1"
BUTTON_BG = "#6A994E"
BUTTON_FG = "white"
STANDARD_PADDING = 10
BUTTON_SIZE = 2
STANDARD_RELIEF = "flat"
BOX_WIDTH = 40
BOX_HEIGHT = 4

# Unicode symbols for buttons (more compatible with Raspberry Pi)
CAMERA_ICON = "📷"
MIC_ICON = "🎙"
TASK_ICON = "📝"
DONE_ICON = "✓"
SNOOZE_ICON = "⏰"
PLAY_ICON = "▶"
PAUSE_ICON = "⏸"
RESUME_ICON = "⟳"
STOP_ICON = "⏹"
EMERGENCY_ICON = "⚠"
SHUTDOWN_ICON = "⏻"

# Initialize pygame mixer
pygame.mixer.init()

# Add new global variables
task_check_thread = None
stop_task_check = threading.Event()

# Flask Camera Server Control
flask_server_process = None
flask_server_running = False

# Camera server functions
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
        try:
            camera.release()
            logger.info("Camera released successfully")
        except Exception as e:
            logger.error(f"Error releasing camera: {e}")

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
                # Convert frame to JPEG with quality settings
                ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    # Yield the frame in MJPEG format
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            else:
                time.sleep(0.1)

def start_camera_server():
    """Start the Flask camera server"""
    global camera_server, is_streaming, camera_thread, flask_server_running
    
    if flask_server_running:
        logger.info("Flask camera server already running.")
        return
    try:
        if camera_server is None:
            camera_server = Flask(__name__)
            
            @camera_server.route('/')
            def index():
                return "USB Camera Streaming Server"
            
            @camera_server.route('/start-stream', methods=['POST'])
            def start_stream():
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
            
            @camera_server.route('/stop-stream', methods=['POST'])
            def stop_stream():
                global is_streaming
                
                try:
                    if not is_streaming:
                        return jsonify({"status": "success", "message": "Camera already stopped"})
                    
                    release_camera()
                    return jsonify({"status": "success", "message": "Camera stream stopped"})
                except Exception as e:
                    logger.error(f"Error stopping stream: {e}")
                    return jsonify({"status": "error", "message": str(e)}), 500
            
            @camera_server.route('/stream')
            def video_feed():
                return Response(generate_frames(),
                              mimetype='multipart/x-mixed-replace; boundary=frame')
            
            @camera_server.route('/status')
            def status():
                return jsonify({
                    "status": "success",
                    "is_streaming": is_streaming,
                    "camera_initialized": camera is not None
                })
            
            # Start the Flask server in a separate thread
            server_thread = threading.Thread(target=lambda: camera_server.run(host='0.0.0.0', port=5000, threaded=True))
            server_thread.daemon = True
            server_thread.start()
            
            logger.info("Camera server started on port 5000")
            flask_server_running = True
            return True
    except Exception as e:
        logger.error(f"Error starting camera server: {e}")
        return False

def show_camera():
    """Show the camera stream in a web browser"""
    try:
        # Always open the stream in the default web browser
        import webbrowser
        webbrowser.open('http://localhost:5000/stream')
        messagebox.showinfo("Camera Stream", 
                          f"Camera stream opened in browser!\n\n"
                          f"Local URL: http://localhost:5000/stream\n"
                          f"Network URL: http://<raspberry-pi-ip>:5000/stream")
    except Exception as e:
        logger.error(f"Error starting camera stream: {e}")
        messagebox.showerror("Camera Error", f"Failed to start camera stream: {e}")

def fetch_user_data():
    global user_name, user_profile_pic_url
    try:
        # Get the specific user document using the ID from the screenshot
        user_doc = db.collection('users').document('3Vh88LDtQCeWWwMqCoOM01iqRKA3').get()
        
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_name = user_data.get('name', 'User')
            user_profile_pic_url = user_data.get('profileImageUrl')
            
            logging.debug(f"Fetched user data - Name: {user_name}")
            logging.debug(f"Profile URL: {user_profile_pic_url}")
            
            # Update the greeting label immediately if it exists
            if 'greeting_label' in globals():
                greet_user()
                
            # Update profile picture if URL exists
            if user_profile_pic_url and 'profile_label' in globals():
                try:
                    response = requests.get(user_profile_pic_url)
                    if response.status_code == 200:
                        image_data = response.content
                        image = Image.open(io.BytesIO(image_data))
                        image = image.resize((100, 100), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(image)
                        profile_label.config(image=photo)
                        profile_label.image = photo  # Keep a reference
                    else:
                        logging.error(f"Failed to download profile image. Status code: {response.status_code}")
                except Exception as e:
                    logging.error(f"Error loading profile picture: {e}")
                    profile_label.config(text="No Profile Picture")
        else:
            logging.error("User document not found")
            messagebox.showerror("Error", "User not found in database")
            
    except Exception as e:
        logging.error(f"Error fetching user data: {e}")
        messagebox.showerror("Error", f"Failed to fetch user data: {e}")

def fetch_current_task():
    global current_task, task_sent_time, task_due_time
    try:
        # Get all tasks and filter in memory to avoid index requirement
        tasks_ref = db.collection('tasks')
        tasks = tasks_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).get()
        
        task_found = False
        for task_doc in tasks:
            task_data = task_doc.to_dict()
            # Check if task is not completed
            if not task_data.get('isCompleted', False):
                current_task = task_data.get('task', None)
                task_sent_time = task_data.get('sentTime', None)
                task_due_time = task_data.get('dueTime', None)
                task_found = True
                
                if current_task:
                    task_text = f"Task: {current_task}\nSent: {task_sent_time}"
                    if task_due_time:
                        task_text += f"\nDue: {task_due_time}"
                    task_display.config(text=task_text)
                else:
                    task_display.config(text="No current task.")
                
                logging.debug(f"Fetched task: {current_task}, {task_sent_time}, {task_due_time}")
                break
        
        if not task_found:
            task_display.config(text="No current task.")
            current_task = None
            task_sent_time = None
            task_due_time = None
            
    except Exception as e:
        logging.error(f"Error fetching task: {e}")
        messagebox.showerror("Error", f"Failed to fetch task: {e}")

def greet_user():
    current_hour = datetime.now().hour
    if current_hour < 12:
        greeting = "Good morning"
    elif 12 <= current_hour < 16:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"
    greeting_label.config(text=f"{greeting}, {user_name}")

def emergency_pressed():
    try:
        # Create emergency notification in Firestore
        emergency_data = {
            'type': 'emergency',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'status': 'active',
            'message': 'Emergency alert triggered from Raspberry Pi'
        }
        
        db.collection('emergency_notifications').add(emergency_data)
        
        # Show emergency alert with sound
        root.bell()  # System beep
        messagebox.showwarning("EMERGENCY", "Emergency alert sent to the app!")
        logging.debug("Emergency notification sent to Firestore")
    except Exception as e:
        logging.error(f"Error sending emergency notification: {e}")
        messagebox.showerror("Error", f"Failed to send emergency notification: {e}")

def shutdown_pi():
    """Shutdown the Raspberry Pi"""
    if messagebox.askyesno("Shutdown", "Are you sure you want to shutdown the Raspberry Pi?"):
        shutdown_flask_server()  # Stop Flask server first
        os.system("sudo shutdown -h now")

def find_usb_microphone():
    """Find the USB microphone device index"""
    try:
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            # Look for USB microphone in device name
            if 'USB' in device['name'] and device['max_input_channels'] > 0:
                logger.info(f"Found USB microphone: {device['name']} at index {i}")
                return i
        # If no USB mic found, return default input device
        default_input = sd.default.device[0]
        logger.info(f"Using default input device: {devices[default_input]['name']}")
        return default_input
    except Exception as e:
        logger.error(f"Error finding microphone: {e}")
        return None

def start_recording():
    """Start recording from USB microphone"""
    global is_recording, recording_thread, recording_buffer
    try:
        # Find USB microphone
        mic_index = find_usb_microphone()
        if mic_index is None:
            messagebox.showerror("Recording Error", "No microphone found")
            return

        is_recording = True
        recording_buffer = []
        record_voice_btn.config(bg="red", text="⏹️")
        logging.debug("Recording started.")

        def record_audio():
            fs = 16000  # Sample rate
            channels = 1  # Mono recording
            try:
                with sd.InputStream(device=mic_index,
                                  samplerate=fs,
                                  channels=channels,
                                  dtype='float32',
                                  callback=audio_callback):
                    while is_recording:
                        sd.sleep(100)
            except Exception as e:
                messagebox.showerror("Recording Error", f"An error occurred while recording: {e}")
                logging.error(f"Recording Error: {e}")

        def audio_callback(indata, frames, time, status):
            if status:
                logging.warning(f"Recording status: {status}")
            recording_buffer.append(indata.copy())

        recording_thread = threading.Thread(target=record_audio, daemon=True)
        recording_thread.start()

    except Exception as e:
        logging.error(f"Error starting recording: {e}")
        messagebox.showerror("Recording Error", f"Failed to start recording: {e}")
        is_recording = False
        record_voice_btn.config(bg=BUTTON_BG, text=MIC_ICON)

def stop_recording():
    """Stop recording and save the audio file"""
    global is_recording, recording_thread, recording_buffer
    try:
        is_recording = False
        record_voice_btn.config(bg=BUTTON_BG, text=MIC_ICON)

        if recording_thread and recording_thread.is_alive():
            recording_thread.join()
            logging.debug("Recording thread stopped.")

        if recording_buffer:
            fs = 16000
            filename_wav = f"voice_note_{int(time.time())}.wav"
            filename_mp3 = filename_wav.replace(".wav", ".mp3")

            # Concatenate all recorded chunks
            audio_data = np.concatenate(recording_buffer, axis=0)
            
            # Normalize the audio
            audio_data = audio_data / np.max(np.abs(audio_data))
            audio_data_int16 = np.int16(audio_data * 32767)

            # Save as WAV
            write(filename_wav, fs, audio_data_int16)

            try:
                # Convert to MP3
                sound = AudioSegment.from_wav(filename_wav)
                sound.export(filename_mp3, format="mp3")
                os.remove(filename_wav)
                
                messagebox.showinfo("Saved", f"Voice note saved as {filename_mp3}. Uploading to Firebase...")
                upload_to_firebase(filename_mp3)
            except Exception as e:
                messagebox.showerror("Conversion Error", f"Failed to convert to MP3: {e}")
                logging.error(f"MP3 Conversion Error: {e}")
        else:
            messagebox.showinfo("Recording", "No audio recorded")
    except Exception as e:
        logging.error(f"Error stopping recording: {e}")
        messagebox.showerror("Recording Error", f"Failed to stop recording: {e}")

def toggle_record_voice():
    """Toggle voice recording"""
    if is_recording:
        stop_recording()
    else:
        start_recording()

def upload_to_firebase(local_path):
    try:
        blob = bucket.blob(f"voice_notes/{os.path.basename(local_path)}")
        blob.upload_from_filename(local_path)
        os.remove(local_path)
        messagebox.showinfo("Uploaded", f"Uploaded {os.path.basename(local_path)} to Firebase Storage.")
    except Exception as e:
        messagebox.showerror("Upload Error", f"Failed to upload: {e}")
        logger.error(f"Upload Error: {e}")

def task_done():
    global current_task, task_sent_time, task_due_time
    if current_task:
        try:
            # Update task status in Firestore
            tasks_ref = db.collection('tasks')
            tasks = tasks_ref.where('task', '==', current_task).get()
            
            for task_doc in tasks:
                task_doc.reference.update({
                    'isCompleted': True,
                    'completedAt': firestore.SERVER_TIMESTAMP
                })
            
            messagebox.showinfo("Task Done", "Task marked as done and updated to the app.")
            
            # Clear current task and fetch next task
            current_task = None
            task_sent_time = None
            task_due_time = None
            
            # Fetch the next task
            fetch_current_task()
            
        except Exception as e:
            logging.error(f"Error updating task status: {e}")
            messagebox.showerror("Error", f"Failed to update task status: {e}")
    else:
        messagebox.showinfo("No Task", "No task to mark as done.")

def add_new_task(task, sent_time, due_time=None):
    global current_task, task_sent_time, task_due_time
    try:
        # Create task data
        task_data = {
            'task': task,
            'scheduledTime': int(sent_time.timestamp() * 1000),
            'timestamp': firestore.SERVER_TIMESTAMP,
            'isCompleted': False
        }
        
        # Add due time if provided
        if due_time:
            task_data['dueTime'] = int(due_time.timestamp() * 1000)
        
        # Add to Firestore
        db.collection('tasks').add(task_data)
        
        # Update local variables
        current_task = task
        task_sent_time = sent_time
        task_due_time = due_time
        
        # Update display
        update_task_display()
        
        messagebox.showinfo("Success", "Task added successfully!")
        
    except Exception as e:
        logging.error(f"Error adding task: {e}")
        messagebox.showerror("Error", f"Failed to add task: {e}")

def update_task_display():
    global current_task, task_sent_time, task_due_time
    
    if current_task:
        task_text = f"Task: {current_task}\nScheduled: {task_sent_time.strftime('%Y-%m-%d %H:%M')}"
        if task_due_time:
            task_text += f"\nDue: {task_due_time.strftime('%Y-%m-%d %H:%M')}"
        task_display.config(text=task_text)
    else:
        task_display.config(text="No current task.")

def snooze_task():
    global current_task, task_sent_time, task_due_time, snooze_timer
    
    if current_task:
        try:
            # Cancel any existing snooze timer
            if snooze_timer:
                snooze_timer.cancel()
            
            # Create new snooze time (5 minutes from now)
            snooze_time = datetime.now() + timedelta(minutes=5)
            
            # Update task in Firestore with new due time
            tasks_ref = db.collection('tasks')
            tasks = tasks_ref.where('task', '==', current_task).get()
            
            for task_doc in tasks:
                task_doc.reference.update({
                    'dueTime': int(snooze_time.timestamp() * 1000),
                    'snoozed': True,
                    'snoozeCount': firestore.Increment(1)
                })
            
            # Update local variables
            task_due_time = snooze_time
            
            # Update display
            update_task_display()
            
            # Set timer for notification
            snooze_timer = threading.Timer(300, lambda: show_snooze_notification(current_task))
            snooze_timer.daemon = True
            snooze_timer.start()
            
            messagebox.showinfo("Snooze", f"Task snoozed for 5 minutes until {snooze_time.strftime('%H:%M')}")
            
        except Exception as e:
            logging.error(f"Error snoozing task: {e}")
            messagebox.showerror("Error", f"Failed to snooze task: {e}")
    else:
        messagebox.showinfo("No Task", "No task to snooze.")

def show_snooze_notification(task_name):
    messagebox.showinfo("Task Reminder", f"Your snoozed task '{task_name}' is due now!")

def open_task_scheduler():
    pass  # Removed task adding functionality

def fetch_recordings():
    try:
        # Get recordings from Firestore instead of Storage
        recordings_ref = db.collection('recordings')
        recordings = recordings_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).get()
        
        recordings_list = []
        for doc in recordings:
            data = doc.to_dict()
            recordings_list.append({
                'id': doc.id,
                'name': data.get('name', 'Unnamed Recording'),
                'downloadUrl': data.get('downloadUrl', '')
            })
        
        logging.debug(f"Fetched recordings: {len(recordings_list)}")
        return recordings_list
    except Exception as e:
        logging.error(f"Error fetching recordings: {e}")
        return []

def convert_mp3_to_wav(mp3_path):
    """Convert MP3 to WAV using ffmpeg directly on Raspberry Pi"""
    wav_path = mp3_path.replace(".mp3", ".wav")
    try:
        # Use ffmpeg directly on Raspberry Pi
        subprocess.run([
            "/usr/bin/ffmpeg",
            '-i', mp3_path,
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '1',
            wav_path
        ], check=True, capture_output=True)
        return wav_path
    except subprocess.CalledProcessError as e:
        logging.error(f"FFmpeg conversion error: {e.stderr.decode()}")
        raise
    except Exception as e:
        logging.error(f"Conversion error: {e}")
        raise

def play_recording(recording):
    global is_playing, playback_thread, audio_data, sample_rate, playback_position, playback_duration, playback_stop_event
    try:
        if not recording or 'downloadUrl' not in recording:
            messagebox.showerror("Playback Error", "Invalid recording data")
            return
            
        download_url = recording['downloadUrl']
        if not download_url:
            messagebox.showerror("Playback Error", "No download URL available")
            return
        
        logging.debug(f"Starting playback for: {recording['name']}")
        logging.debug(f"Download URL: {download_url}")
        
        # Stop any current playback
        stop_playback()
        
        # Download the file using requests
        response = requests.get(download_url, stream=True)
        if response.status_code != 200:
            messagebox.showerror("Playback Error", f"Failed to download audio: HTTP {response.status_code}")
            return
            
        # Create a temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()
        
        logging.debug(f"Saving downloaded file to: {temp_path}")
        
        # Save the downloaded content to the temporary file
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        try:
            logging.debug("Converting MP3 to WAV...")
            # Convert MP3 to WAV using our helper function
            wav_path = convert_mp3_to_wav(temp_path)
            
            logging.debug("Reading WAV file...")
            # Read the WAV file
            audio_data, sample_rate = sf.read(wav_path)
            
            logging.debug(f"Audio data shape: {audio_data.shape}, Sample rate: {sample_rate}")
            logging.debug(f"Audio data type: {audio_data.dtype}")
            
            # Convert to float32 if needed
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # If stereo, convert to mono
            if len(audio_data.shape) > 1:
                logging.debug("Converting stereo to mono")
                audio_data = audio_data.mean(axis=1)
            
            # Normalize audio
            max_val = np.max(np.abs(audio_data))
            if max_val > 0:
                audio_data = audio_data / max_val
            
            playback_duration = len(audio_data) / sample_rate
            playback_position = 0
            
            logging.debug(f"Audio duration: {playback_duration:.2f} seconds")
            
            # Start playback in a separate thread
            playback_stop_event.clear()
            playback_thread = threading.Thread(target=playback_audio, args=(audio_data, sample_rate))
            playback_thread.daemon = True
            playback_thread.start()
            
            is_playing = True
            update_playback_status()
            
            # Add to temp files for cleanup
            temp_files.append(temp_path)
            temp_files.append(wav_path)
            
            logging.debug(f"Started playback thread for: {recording['name']}")
            
        except Exception as e:
            logging.error(f"Error converting or playing audio: {str(e)}", exc_info=True)
            messagebox.showerror("Playback Error", f"Failed to play recording: {str(e)}")
            
    except Exception as e:
        logging.error(f"Playback Error: {str(e)}", exc_info=True)
        messagebox.showerror("Playback Error", f"Failed to play recording: {str(e)}")

def playback_audio(audio_data, sample_rate):
    global playback_position, is_playing
    
    try:
        logging.debug(f"Setting up audio stream with sample rate: {sample_rate}")
        # Get default output device info
        device_info = sd.query_devices(kind='output')
        logging.debug(f"Using output device: {device_info['name']}")
        
        # Set up the audio stream
        with sd.OutputStream(samplerate=sample_rate, channels=1, dtype=np.float32) as stream:
            logging.debug("Audio stream opened successfully")
            # Calculate chunk size (100ms of audio)
            chunk_size = int(sample_rate * 0.1)
            
            # Play audio in chunks
            for i in range(0, len(audio_data), chunk_size):
                if playback_stop_event.is_set():
                    logging.debug("Playback stopped by user")
                    break
                
                # Get the current chunk
                chunk_end = min(i + chunk_size, len(audio_data))
                chunk = audio_data[i:chunk_end]
                
                try:
                    # Write the chunk to the stream
                    stream.write(chunk)
                    # Update position
                    playback_position = i / sample_rate
                except Exception as e:
                    logging.error(f"Error writing to audio stream: {str(e)}", exc_info=True)
                    break
            
            # Ensure the stream is drained
            stream.stop()
            logging.debug("Audio stream closed")
        
        # Playback completed
        is_playing = False
        playback_position = 0
        update_playback_status()
        logging.debug("Playback completed successfully")
        
    except Exception as e:
        logging.error(f"Error during playback: {str(e)}", exc_info=True)
        is_playing = False
        update_playback_status()
        messagebox.showerror("Playback Error", f"Error during playback: {str(e)}")

def update_playback_status():
    # Update UI to reflect current playback status
    if is_playing:
        play_btn.config(state="disabled")
        pause_btn.config(state="normal")
        resume_btn.config(state="disabled")
        stop_btn.config(state="normal")
    else:
        play_btn.config(state="normal")
        pause_btn.config(state="disabled")
        resume_btn.config(state="disabled")
        stop_btn.config(state="disabled")

def pause_recording():
    global is_playing
    try:
        if is_playing:
            playback_stop_event.set()
            is_playing = False
            update_playback_status()
            logging.debug("Playback paused")
        else:
            messagebox.showinfo("Pause Error", "No playback to pause.")
    except Exception as e:
        messagebox.showerror("Pause Error", f"Failed to pause playback: {e}")
        logging.error(f"Pause Error: {e}")

def resume_recording():
    global is_playing, playback_thread, playback_position
    try:
        if not is_playing and audio_data is not None:
            logging.debug(f"Resuming playback from position: {playback_position:.2f} seconds")
            # Calculate the remaining audio
            start_sample = int(playback_position * sample_rate)
            remaining_audio = audio_data[start_sample:]
            
            # Start playback from where we left off
            playback_stop_event.clear()
            playback_thread = threading.Thread(target=playback_audio, args=(remaining_audio, sample_rate))
            playback_thread.daemon = True
            playback_thread.start()
            
            is_playing = True
            update_playback_status()
            logging.debug("Playback resumed successfully")
        else:
            logging.debug("No paused playback to resume")
            messagebox.showinfo("Resume Error", "No paused playback to resume.")
    except Exception as e:
        logging.error(f"Resume Error: {str(e)}", exc_info=True)
        messagebox.showerror("Resume Error", f"Failed to resume playback: {str(e)}")

def stop_playback():
    global is_playing, playback_position
    try:
        logging.debug("Stopping playback...")
        playback_stop_event.set()
        sd.stop()  # Stop any ongoing playback
        is_playing = False
        playback_position = 0
        update_playback_status()
        logging.debug("Playback stopped successfully")
    except Exception as e:
        logging.error(f"Error stopping playback: {str(e)}", exc_info=True)

def update_media_player():
    recordings = fetch_recordings()
    if recordings:
        media_listbox.delete(0, tk.END)
        for recording in recordings:
            media_listbox.insert(tk.END, recording['name'])
    else:
        media_listbox.insert(tk.END, "No recordings available.")

def cleanup_temp_files():
    global temp_files
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception as e:
            logging.error(f"Failed to delete temp file {temp_file}: {e}")

# Add after Firebase initialization
def setup_realtime_listeners():
    # Listen for user profile changes
    def on_user_snapshot(doc_snapshot, changes, read_time):
        for doc in doc_snapshot:
            if doc.exists:
                user_data = doc.to_dict()
                update_profile(user_data)

    # Listen for task changes
    def on_task_snapshot(doc_snapshot, changes, read_time):
        for doc in doc_snapshot:
            if doc.exists:
                task_data = doc.to_dict()
                update_task(task_data)

    # Listen for recording changes
    def on_recording_snapshot(doc_snapshot, changes, read_time):
        for doc in doc_snapshot:
            if doc.exists:
                recording_data = doc.to_dict()
                update_recordings()

    # Set up the listeners
    user_ref = db.collection('users').document('3Vh88LDtQCeWWwMqCoOM01iqRKA3')
    user_ref.on_snapshot(on_user_snapshot)

    tasks_ref = db.collection('tasks')
    tasks_ref.on_snapshot(on_task_snapshot)

    recordings_ref = db.collection('recordings')
    recordings_ref.on_snapshot(on_recording_snapshot)

def update_profile(user_data):
    global user_name, user_profile_pic_url
    try:
        user_name = user_data.get('name', 'User')
        new_profile_pic_url = user_data.get('profileImageUrl')
        
        # Only update if the URL has changed
        if new_profile_pic_url != user_profile_pic_url:
            user_profile_pic_url = new_profile_pic_url
            if user_profile_pic_url:
                try:
                    response = requests.get(user_profile_pic_url)
                    if response.status_code == 200:
                        image_data = response.content
                        image = Image.open(io.BytesIO(image_data))
                        image = image.resize((100, 100), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(image)
                        profile_label.config(image=photo)
                        profile_label.image = photo
                except Exception as e:
                    logging.error(f"Error updating profile picture: {e}")
        
        # Update greeting
        greet_user()
    except Exception as e:
        logging.error(f"Error updating profile: {e}")

def update_task(task_data):
    global current_task, task_sent_time, task_due_time
    try:
        # Only update if the task is not completed
        if not task_data.get('isCompleted', False):
            current_task = task_data.get('task')
            task_sent_time = task_data.get('sentTime')
            task_due_time = task_data.get('dueTime')
            
            if current_task:
                task_text = f"Task: {current_task}\nSent: {task_sent_time}"
                if task_due_time:
                    task_text += f"\nDue: {task_due_time}"
                task_display.config(text=task_text)
            else:
                task_display.config(text="No current task.")
                current_task = None
                task_sent_time = None
                task_due_time = None
    except Exception as e:
        logging.error(f"Error updating task: {e}")

def update_recordings():
    try:
        recordings = fetch_recordings()
        media_listbox.delete(0, tk.END)
        if recordings:
            for recording in recordings:
                media_listbox.insert(tk.END, recording['name'])
        else:
            media_listbox.insert(tk.END, "No recordings available.")
    except Exception as e:
        logging.error(f"Error updating recordings: {e}")

def play_task_audio(audio_url):
    try:
        # Download the audio file
        response = requests.get(audio_url)
        if response.status_code == 200:
            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            temp_path = temp_file.name
            temp_file.close()
            
            with open(temp_path, 'wb') as f:
                f.write(response.content)
            
            # Convert to WAV for pygame
            wav_path = convert_mp3_to_wav(temp_path)
            
            # Play the audio
            pygame.mixer.music.load(wav_path)
            pygame.mixer.music.play()
            
            # Wait for audio to finish
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # Cleanup
            os.remove(temp_path)
            os.remove(wav_path)
            
    except Exception as e:
        logging.error(f"Error playing task audio: {e}")

def check_scheduled_tasks():
    while not stop_task_check.is_set():
        try:
            current_time = datetime.now()
            tasks_ref = db.collection('tasks')
            tasks = tasks_ref.where('isCompleted', '==', False).get()
            
            for task_doc in tasks:
                task_data = task_doc.to_dict()
                scheduled_time = datetime.fromtimestamp(task_data.get('scheduledTime', 0) / 1000)
                
                # Check if it's time to play the audio
                if (current_time - scheduled_time).total_seconds() < 5 and \
                   (current_time - scheduled_time).total_seconds() > 0:
                    # Check if task has audio
                    if 'recordingUrl' in task_data:
                        # Play audio in a separate thread
                        audio_thread = threading.Thread(
                            target=play_task_audio,
                            args=(task_data['recordingUrl'],)
                        )
                        audio_thread.daemon = True
                        audio_thread.start()
            
            # Sleep for a short time before next check
            time.sleep(1)
            
        except Exception as e:
            logging.error(f"Error checking scheduled tasks: {e}")
            time.sleep(5)  # Sleep longer on error

def start_task_checker():
    global task_check_thread
    if task_check_thread is None or not task_check_thread.is_alive():
        stop_task_check.clear()
        task_check_thread = threading.Thread(target=check_scheduled_tasks)
        task_check_thread.daemon = True
        task_check_thread.start()

def stop_task_checker():
    stop_task_check.set()
    if task_check_thread:
        task_check_thread.join(timeout=1)

def upload_ngrok_url_to_firebase():
    print("Starting ngrok URL upload...")
    time.sleep(2)
    try:
        tunnels = requests.get("http://localhost:4040/api/tunnels").json()
        public_url = None
        for tunnel in tunnels['tunnels']:
            if tunnel['proto'] == 'https':
                public_url = tunnel['public_url']
                break
        print(f"ngrok public_url: {public_url}")
        if public_url:
            db.collection('camera').document('stream').set({'url': public_url})
            logger.info(f"Uploaded ngrok URL to Firebase: {public_url}")
            print(f"Uploaded ngrok URL to Firebase: {public_url}")
        else:
            logger.error("No ngrok public URL found.")
            print("No ngrok public URL found.")
    except Exception as e:
        logger.error(f"Error uploading ngrok URL to Firebase: {e}")
        print(f"Error uploading ngrok URL to Firebase: {e}")

def launch_flask_server():
    """Launch the Flask server and start camera, then start ngrok and upload URL to Firebase"""
    global flask_server_process, flask_server_running
    try:
        if flask_server_running:
            messagebox.showinfo("Flask Server", "Flask server is already running!")
            return
        # Launch Flask server in a separate process
        flask_server_process = subprocess.Popen(['python', 'camera_server.py'],
                                              stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE)
        # Wait a moment to check if server started successfully
        time.sleep(2)
        if flask_server_process.poll() is None:  # Process is still running
            flask_server_running = True
            flask_status_label.config(text="Flask Server: Running", fg="green")
            # Start ngrok in a subprocess
            ngrok_process = subprocess.Popen(['ngrok', 'http', '5000'],
                                             stdout=subprocess.PIPE,
                                             stderr=subprocess.PIPE)
            # Wait a moment for ngrok to start
            time.sleep(3)
            # Upload ngrok URL to Firebase
            upload_ngrok_url_to_firebase()
            # Start the camera stream
            try:
                response = requests.post('http://localhost:5000/start-stream')
                if response.status_code == 200:
                    messagebox.showinfo("Flask Server", 
                        "Flask server, camera, and ngrok started successfully!\n\n"
                        "You can view the camera feed at the ngrok URL in Firebase.")
                else:
                    messagebox.showwarning("Camera Warning", 
                        "Server started but camera failed to start. Please try again.")
            except Exception as e:
                messagebox.showwarning("Camera Warning", 
                    f"Server started but camera failed to start: {e}")
        else:
            # Get error output if process failed
            _, stderr = flask_server_process.communicate()
            error_msg = stderr.decode() if stderr else "Unknown error"
            flask_server_running = False
            flask_status_label.config(text="Flask Server: Failed", fg="red")
            messagebox.showerror("Flask Server Error", f"Failed to start Flask server:\n{error_msg}")
    except Exception as e:
        flask_server_running = False
        flask_status_label.config(text="Flask Server: Error", fg="red")
        messagebox.showerror("Flask Server Error", f"Error launching Flask server: {e}")

def shutdown_flask_server():
    """Shutdown the Flask server"""
    global flask_server_process, flask_server_running
    
    if flask_server_process and flask_server_running:
        try:
            flask_server_process.terminate()
            flask_server_process.wait(timeout=5)
            flask_server_running = False
            flask_status_label.config(text="Flask Server: Stopped", fg="black")
        except Exception as e:
            messagebox.showerror("Flask Server Error", f"Error stopping Flask server: {e}")

# Add Flask server toggle function
def toggle_flask_server():
    """Toggle the Flask server on/off"""
    global flask_server_running, flask_server_process
    
    if flask_server_running:
        # Stop the server
        try:
            # First stop the camera stream
            requests.post('http://localhost:5000/stop-stream')
            # Then stop the server
            flask_server_process.terminate()
            flask_server_process.wait(timeout=5)
            flask_server_running = False
            flask_status_label.config(text="Flask Server: Stopped", fg="black")
            messagebox.showinfo("Flask Server", "Flask server stopped successfully!")
        except Exception as e:
            messagebox.showerror("Flask Server Error", f"Error stopping Flask server: {e}")
    else:
        # Start the server
        launch_flask_server()

# Create the main window and UI elements
root = tk.Tk()
root.title("Care Taker Bot")
root.geometry("800x480")
root.configure(bg=STANDARD_BG)

# Title
tk.Label(root, text="CARE TAKER BOT", font=TITLE_FONT, bg=STANDARD_BG, fg="#333").pack(pady=10)

# Left Frame
left_frame = tk.Frame(root, bg=STANDARD_BG)
left_frame.place(x=20, y=60)

# Profile Picture
profile_label = tk.Label(left_frame, bg=STANDARD_BG, width=100, height=100)
profile_label.pack(pady=5)

# Initialize profile picture
if user_profile_pic_url:
    try:
        response = requests.get(user_profile_pic_url)
        if response.status_code == 200:
            image_data = response.content
            image = Image.open(io.BytesIO(image_data))
            image = image.resize((100, 100), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            profile_label.config(image=photo)
            profile_label.image = photo  # Keep a reference
        else:
            logging.error(f"Failed to download profile image. Status code: {response.status_code}")
            profile_label.config(text="No Profile Picture")
    except Exception as e:
        logging.error(f"Error loading profile picture: {e}")
        profile_label.config(text="No Profile Picture")
else:
    profile_label.config(text="No Profile Picture")

# Greeting Label
greeting_label = tk.Label(left_frame, text="", bg=STANDARD_BG, fg="#333", wraplength=150, 
                         justify="center", font=STANDARD_FONT)
greeting_label.pack(pady=5)

# Update button styles
def create_emergency_button(parent, text, command, bg_color="#D9534F"):
    return tk.Button(parent,
                    text=text,
                    command=command,
                    bg=bg_color,
                    fg="white",
                    font=("DejaVu Sans", 10),  # Smaller font
                    width=15,  # Reduced width
                    height=1,  # Reduced height
                    relief=STANDARD_RELIEF,
                    borderwidth=1)  # Thinner border

def create_action_button(parent, text, command, bg_color=BUTTON_BG):
    return tk.Button(parent,
                    text=text,
                    command=command,
                    bg=bg_color,
                    fg=BUTTON_FG,
                    font=BUTTON_FONT,
                    width=2,
                    height=1,
                    relief=STANDARD_RELIEF,
                    borderwidth=1)

# Update the emergency and shutdown buttons
emergency_btn = create_emergency_button(left_frame,
                                     f"{EMERGENCY_ICON} Emergency",
                                     emergency_pressed)
emergency_btn.pack(pady=2)

shutdown_btn = create_emergency_button(left_frame,
                                      f"{SHUTDOWN_ICON} Shutdown",
                                      shutdown_pi,
                                      bg_color="#555")
shutdown_btn.pack(pady=2)

# Add Flask server button and status label
flask_btn = create_emergency_button(left_frame,
                                  "🚀 Launch Flask Server",
                                  launch_flask_server,
                                  bg_color="#4CAF50")
flask_btn.pack(pady=2)

# Add Flask server toggle button
flask_toggle_btn = create_emergency_button(left_frame,
                                         "🔒 Toggle Flask Server",
                                         lambda: toggle_flask_server(),
                                         bg_color="#FFA500")
flask_toggle_btn.pack(pady=2)

flask_status_label = tk.Label(left_frame,
                            text="Flask Server: Stopped",
                            bg=STANDARD_BG,
                            fg="black",
                            font=STANDARD_FONT)
flask_status_label.pack(pady=2)

# Camera Frame
camera_frame = tk.Frame(root, bg=STANDARD_BG)
camera_frame.place(x=230, y=70)

camera_btn = tk.Button(camera_frame,
                      text=f"{CAMERA_ICON} Open Camera View",
                      command=show_camera,
                      font=BUTTON_FONT,
                      bg=BUTTON_BG,
                      fg=BUTTON_FG,
                      width=BOX_WIDTH,
                      height=BOX_HEIGHT,
                      relief=STANDARD_RELIEF)
camera_btn.grid(row=0, column=0, padx=STANDARD_PADDING)

record_voice_btn = tk.Button(camera_frame,
                           text=MIC_ICON,
                           command=toggle_record_voice,
                           bg=BUTTON_BG,
                           fg=BUTTON_FG,
                           font=BUTTON_FONT,
                           width=2,
                           height=1,
                           relief=STANDARD_RELIEF)
record_voice_btn.grid(row=0, column=1, padx=STANDARD_PADDING)

# Task Frame
task_frame = tk.Frame(root, bg=STANDARD_BG)
task_frame.place(x=230, y=200)

task_display = tk.Label(task_frame, text="Loading task...", font=STANDARD_FONT, bg=STANDARD_BG, 
                       fg="#333", wraplength=500, justify="center", relief="solid", 
                       width=BOX_WIDTH, height=BOX_HEIGHT)
task_display.grid(row=0, column=0, padx=10)

# Task done button
task_done_btn = tk.Button(task_frame,
                         text=DONE_ICON,
                         command=task_done,
                         bg=BUTTON_BG,
                         fg=BUTTON_FG,
                         font=BUTTON_FONT,
                         width=2,
                         height=1,
                         relief=STANDARD_RELIEF)
task_done_btn.grid(row=0, column=1, padx=5)

# Snooze button
snooze_btn = tk.Button(task_frame,
                      text=SNOOZE_ICON,
                      command=snooze_task,
                      bg=BUTTON_BG,
                      fg=BUTTON_FG,
                      font=BUTTON_FONT,
                      width=2,
                      height=1,
                      relief=STANDARD_RELIEF)
snooze_btn.grid(row=0, column=2, padx=5)

# Media Frame
media_frame = tk.Frame(root, bg=STANDARD_BG)
media_frame.place(x=230, y=330)

media_listbox = tk.Listbox(media_frame, font=STANDARD_FONT, width=BOX_WIDTH, height=BOX_HEIGHT, 
                          bg=STANDARD_BG, fg="#333")
media_listbox.grid(row=0, column=0, padx=10)

# Create round buttons for media controls
def create_round_button(parent, text, command, bg_color="#6A994E"):
    button = tk.Button(parent, text=text, command=command, bg=bg_color, fg="white", 
                      font=BUTTON_FONT, width=3, height=1, relief="flat")
    # Make the button round
    button.config(borderwidth=0, highlightthickness=0)
    return button

# Function to get the selected recording
def get_selected_recording():
    try:
        selection = media_listbox.curselection()
        if not selection:
            return None
        
        recordings = fetch_recordings()
        if recordings and selection[0] < len(recordings):
            return recordings[selection[0]]
        return None
    except Exception as e:
        logging.error(f"Error getting selected recording: {e}")
        return None

# Play button
play_btn = create_round_button(media_frame, PLAY_ICON,
                             command=lambda: play_recording(get_selected_recording()))
play_btn.grid(row=0, column=1, padx=5)

# Pause button
pause_btn = create_round_button(media_frame, PAUSE_ICON, command=pause_recording)
pause_btn.config(state="disabled")
pause_btn.grid(row=1, column=1, padx=5)

# Resume button
resume_btn = create_round_button(media_frame, RESUME_ICON, command=resume_recording)
resume_btn.config(state="disabled")
resume_btn.grid(row=0, column=2, padx=5)

# Stop button
stop_btn = create_round_button(media_frame, STOP_ICON, command=stop_playback)
stop_btn.config(state="disabled")
stop_btn.grid(row=1, column=2, padx=5)

# Initialize data after UI is created
fetch_user_data()
greet_user()
fetch_current_task()
update_media_player()
setup_realtime_listeners()
start_task_checker()

# Update the cleanup on window close
def on_closing():
    try:
        # Stop task checker
        stop_task_checker()
        
        # Stop Flask server if it's running
        if flask_server_running:
            try:
                # First stop the camera stream
                requests.post('http://localhost:5000/stop-stream')
                # Then stop the server
                flask_server_process.terminate()
                flask_server_process.wait(timeout=5)
                logging.info("Flask server stopped during shutdown")
            except Exception as e:
                logging.error(f"Error stopping Flask server during shutdown: {e}")
        
        # Clean up temporary files
        cleanup_temp_files()
        
        # Destroy the window
        root.destroy()
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
        root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
