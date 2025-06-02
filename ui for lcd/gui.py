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
    'storageBucket': 'project-app-8f1c2.firebasestorage.app'  # Updated bucket name
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
camera = None
camera_thread = None
is_streaming = False
frame = None
frame_lock = threading.Lock()

# Constants for UI consistency
STANDARD_FONT = ("DejaVu Sans", 14)  # Increased font size
TITLE_FONT = ("DejaVu Sans", 28, "bold")
BUTTON_FONT = ("DejaVu Sans", 16)
STANDARD_BG = "#F0F4F8"  # Light blue-gray background
BUTTON_BG = "#4A90E2"  # Modern blue
BUTTON_FG = "white"
STANDARD_PADDING = 15
BUTTON_SIZE = 2
STANDARD_RELIEF = "flat"
BOX_WIDTH = 45
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

# Audio recording variables
audio_recording = []
audio_start_time = None

# --- Smaller button style for 7-inch display ---
def create_small_button(parent, text, command, bg_color, fg_color="white", width=12):
    return tk.Button(parent, text=text, command=command, bg=bg_color, fg=fg_color,
                     font=("DejaVu Sans", 14, "bold"), width=width, height=1, relief="raised", borderwidth=2,
                     activebackground="#444", activeforeground=fg_color)

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
        return True
    try:
        if camera_server is None:
            camera_server = Flask(__name__)
            
            @camera_server.route('/')
            def index():
                return "USB Camera Recording Server"
            
            @camera_server.route('/start-recording', methods=['POST'])
            def start_recording():
                global camera, camera_thread, is_streaming
                
                try:
                    if is_streaming:
                        return jsonify({"status": "error", "message": "Camera already in use"}), 400
                    
                    if not init_camera():
                        return jsonify({"status": "error", "message": "Failed to initialize camera"}), 500
                    
                    # Start recording in a separate thread
                    recording_thread = threading.Thread(target=record_video)
                    recording_thread.daemon = True
                    recording_thread.start()
                    
                    logger.info("Video recording started")
                    return jsonify({"status": "success", "message": "Recording started"})
                except Exception as e:
                    logger.error(f"Error starting recording: {e}")
                    return jsonify({"status": "error", "message": str(e)}), 500
            
            @camera_server.route('/stop-recording', methods=['POST'])
            def stop_recording():
                global is_streaming
                
                try:
                    if not is_streaming:
                        return jsonify({"status": "success", "message": "No recording in progress"})
                    
                    release_camera()
                    return jsonify({"status": "success", "message": "Recording stopped"})
                except Exception as e:
                    logger.error(f"Error stopping recording: {e}")
                    return jsonify({"status": "error", "message": str(e)}), 500
            
            @camera_server.route('/status')
            def status():
                return jsonify({
                    "status": "success",
                    "is_recording": is_streaming,
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
    """Show the camera preview window"""
    camera_preview.start_preview()

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
        current_time = datetime.now()
        for task_doc in tasks:
            task_data = task_doc.to_dict()
            # Check if task is not completed and is due
            if not task_data.get('isCompleted', False):
                scheduled_time = datetime.fromtimestamp(task_data.get('scheduledTime', 0) / 1000)
                # Only show task if it's time to execute (within 5 minutes of scheduled time)
                if abs((current_time - scheduled_time).total_seconds()) <= 300:  # 5 minutes = 300 seconds
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
            task_display.config(text="No tasks due at this time.")
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
    """Start recording video for 10 seconds"""
    global is_recording, recording_thread, recording_buffer
    try:
        # Find USB camera
        if not init_camera():
            messagebox.showerror("Recording Error", "No camera found")
            return

        # Show recording notification (only for video)
        notification_window = tk.Toplevel(root)
        notification_window.title("Recording Notification")
        notification_window.geometry("400x200")
        notification_window.attributes('-topmost', True)
        # Center the notification
        notification_window.update_idletasks()
        width = notification_window.winfo_width()
        height = notification_window.winfo_height()
        x = (notification_window.winfo_screenwidth() // 2) - (width // 2)
        y = (notification_window.winfo_screenheight() // 2) - (height // 2)
        notification_window.geometry(f'{width}x{height}+{x}+{y}')
        # Add warning message
        warning_label = tk.Label(notification_window, 
                               text="⚠️ Recording in Progress ⚠️\n\nYou are being recorded.\nThis recording will be saved and uploaded.",
                               font=("DejaVu Sans", 14, "bold"),
                               fg="red",
                               justify="center")
        warning_label.pack(pady=20)
        # Add countdown label
        countdown_label = tk.Label(notification_window, 
                                 text="Recording will stop in: 10",
                                 font=("DejaVu Sans", 12))
        countdown_label.pack(pady=10)

        is_recording = True
        logging.debug("Recording started.")

        def record_video():
            """Record video for 10 seconds"""
            global camera, is_streaming
            try:
                # Set up video writer
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"video_{timestamp}.mp4"
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(filename, fourcc, 30.0, (640, 480))
                is_streaming = True
                start_time = time.time()
                while is_streaming and (time.time() - start_time) < 10:
                    ret, frame = camera.read()
                    if ret:
                        out.write(frame)
                        time.sleep(0.033)  # ~30 fps
                out.release()
                # Upload to Firebase
                upload_video_to_firebase(filename)
                # Clean up
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception as e:
                logger.error(f"Error recording video: {e}")
                is_streaming = False
            finally:
                # Close the camera preview window
                if camera_preview.window is not None:
                    camera_preview.stop_preview()
                # Release camera resources
                release_camera()
                # Close notification window
                notification_window.destroy()

        recording_thread = threading.Thread(target=record_video, daemon=True)
        recording_thread.start()

    except Exception as e:
        logging.error(f"Error starting recording: {e}")
        messagebox.showerror("Recording Error", f"Failed to start recording: {e}")
        is_recording = False

def stop_recording():
    """Stop recording"""
    global is_recording
    is_recording = False
    record_voice_btn.config(bg=BUTTON_BG, text="Record Voice")
    release_camera()

def upload_video_to_firebase(local_path):
    try:
        # Create a unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}.mp4"
        
        logger.debug(f"Attempting to upload video: {local_path}")
        
        # Create the blob with the correct path for videos
        video_blob = bucket.blob(f"videos/{filename}")
        
        # Upload the file with content type
        video_blob.upload_from_filename(
            local_path,
            content_type='video/mp4'
        )
        
        # Make the file publicly accessible
        video_blob.make_public()
        
        # Get the public URL
        public_url = video_blob.public_url
        
        # Add metadata to Firestore
        db.collection('videos').add({
            'name': filename,
            'url': public_url,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'type': 'video'
        })
        
        messagebox.showinfo("Success", f"Video uploaded successfully!")
        logger.info(f"Successfully uploaded {filename} to Firebase Storage")
        
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        messagebox.showerror("Upload Error", f"Failed to upload video: {str(e)}")

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
        # Get recordings from Firebase Storage (only from recordings folder)
        recordings_ref = bucket.list_blobs(prefix='recordings/')
        
        recordings_list = []
        for blob in recordings_ref:
            # Skip if it's a directory or not in recordings folder
            if not blob.name.endswith('/'):
                # Get the public URL
                blob.make_public()
            recordings_list.append({
                    'id': blob.name,
                    'name': os.path.basename(blob.name),
                    'url': blob.public_url,
                    'timestamp': blob.time_created
                })
        
        # Sort recordings by timestamp (newest first)
        recordings_list.sort(key=lambda x: x['timestamp'], reverse=True)
        
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

def get_selected_recording():
    """Get the currently selected recording from the listbox"""
    try:
        selection = media_listbox.curselection()
        if not selection:
            messagebox.showinfo("Selection Error", "Please select a recording to play")
            return None
            
        # Get the selected item text
        selected_text = media_listbox.get(selection[0])
        
        # Fetch recordings to get the full data
        recordings = fetch_recordings()
        if not recordings:
            return None
            
        # Find the matching recording
        for recording in recordings:
            if recording['name'] in selected_text:
                return recording
                
        return None
    except Exception as e:
        logging.error(f"Error getting selected recording: {e}")
        return None

def play_recording(recording):
    global is_playing, playback_thread, audio_data, sample_rate, playback_position, playback_duration, playback_stop_event
    try:
        if not recording or 'url' not in recording:
            messagebox.showerror("Playback Error", "Invalid recording data")
            return
            
        download_url = recording['url']
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
    """Play audio data through the sound device"""
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
    """Update the state of playback control buttons"""
    if is_playing:
        play_btn.config(state="disabled")
        pause_btn.config(state="normal")
        resume_btn.config(state="disabled")
        stop_btn.config(state="normal")
    else:
        if playback_position > 0:  # If we're paused
            play_btn.config(state="disabled")
            pause_btn.config(state="disabled")
            resume_btn.config(state="normal")
            stop_btn.config(state="normal")
        else:  # If we're stopped
            play_btn.config(state="normal")
            pause_btn.config(state="disabled")
            resume_btn.config(state="disabled")
            stop_btn.config(state="disabled")

def pause_recording():
    """Pause the current playback"""
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
    """Resume playback from where it was paused"""
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
    """Stop the current playback"""
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
            # Format the timestamp for display
            timestamp = recording.get('timestamp')
            if timestamp:
                if isinstance(timestamp, datetime):
                    formatted_time = timestamp.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_time = str(timestamp)
                display_text = f"{recording['name']} ({formatted_time})"
            else:
                display_text = recording['name']
            media_listbox.insert(tk.END, display_text)
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
            
            # Update task display
            fetch_current_task()
            
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
    """This function is deprecated - server is now controlled from the app"""
    pass

def shutdown_flask_server():
    """This function is deprecated - server is now controlled from the app"""
    pass

# Add Flask server toggle function
def toggle_flask_server():
    """This function is deprecated - server is now controlled from the app"""
    pass

# Add new camera preview window class
class CameraPreviewWindow:
    def __init__(self):
        self.window = None
        self.camera = None
        self.is_running = False
        self.preview_label = None
        
    def start_preview(self):
        if self.window is None:
            self.window = tk.Toplevel(root)
            self.window.title("Camera Preview")
            self.window.geometry("640x480")
            
            # Add close button
            close_btn = tk.Button(self.window, text="Close", command=self.stop_preview)
            close_btn.pack(pady=5)
            
            # Add preview label
            self.preview_label = tk.Label(self.window)
            self.preview_label.pack(expand=True, fill='both')
            
            # Initialize camera
            self.camera = cv2.VideoCapture(0)
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            self.is_running = True
            self.update_preview()
            
    def update_preview(self):
        if self.is_running and self.camera is not None:
            ret, frame = self.camera.read()
            if ret:
                # Convert frame to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Convert to PhotoImage
                image = Image.fromarray(frame_rgb)
                photo = ImageTk.PhotoImage(image=image)
                # Update label
                self.preview_label.config(image=photo)
                self.preview_label.image = photo
            # Schedule next update
            self.window.after(10, self.update_preview)
            
    def stop_preview(self):
        self.is_running = False
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        if self.window is not None:
            self.window.destroy()
            self.window = None

# Create camera preview instance
camera_preview = CameraPreviewWindow()

# Add clock update function
def update_clock():
    current_time = datetime.now().strftime("%H:%M")
    clock_label.config(text=current_time)
    root.after(1000, update_clock)  # Still update every second for accuracy

def toggle_record_voice():
    """Toggle voice recording on/off (user controlled duration)"""
    global is_recording, recording_thread, audio_recording, audio_start_time

    if not is_recording:
        try:
            mic_index = find_usb_microphone()
            if mic_index is None:
                messagebox.showerror("Recording Error", "No microphone found")
                return
            is_recording = True
            record_voice_btn.config(bg="red", fg="white", text="Stop Recording")
            logging.debug("Voice recording started.")

            # Start audio recording with improved settings
            audio_start_time = datetime.now()
            sample_rate = 48000  # Increased sample rate for better quality
            audio_recording = []

            def callback(indata, frames, time_info, status):
                if is_recording:
                    # Apply basic noise reduction by removing DC offset and normalizing
                    audio = indata.copy()
                    # Remove DC offset
                    audio = audio - np.mean(audio)
                    # Normalize to prevent clipping
                    max_val = np.max(np.abs(audio))
                    if max_val > 0:
                        audio = audio / max_val * 0.9  # Leave some headroom
                    audio_recording.append(audio)
                else:
                    raise sd.CallbackStop()

            # Start the stream in a thread so the GUI doesn't freeze
            def record_audio_stream():
                # Configure input stream with better settings
                with sd.InputStream(
                    samplerate=sample_rate,
                    channels=1,
                    callback=callback,
                    blocksize=2048,  # Increased block size for better stability
                    dtype=np.float32,
                    device=mic_index
                ) as stream:
                    while is_recording:
                        time.sleep(0.1)

                # Save the recording
                timestamp = audio_start_time.strftime("%Y%m%d_%H%M%S")
                temp_wav = f"temp_{timestamp}.wav"
                temp_mp3 = f"audio_{timestamp}.mp3"
                
                # First save as WAV
                audio_data = np.concatenate(audio_recording, axis=0)
                
                # Apply additional noise reduction
                # Remove DC offset
                audio_data = audio_data - np.mean(audio_data)
                
                # Apply a simple noise gate
                noise_floor = 0.01  # Adjust this value based on your noise level
                audio_data[np.abs(audio_data) < noise_floor] = 0
                
                # Normalize the audio
                max_val = np.max(np.abs(audio_data))
                if max_val > 0:
                    audio_data = audio_data / max_val * 0.9  # Leave some headroom
                
                # Save the processed audio
                sf.write(temp_wav, audio_data, sample_rate)
                
                try:
                    # Convert WAV to MP3 using ffmpeg with improved settings
                    subprocess.run([
                        "/usr/bin/ffmpeg",
                        '-i', temp_wav,
                        '-codec:a', 'libmp3lame',
                        '-qscale:a', '0',  # Highest quality MP3
                        '-ar', '48000',    # Maintain high sample rate
                        '-af', 'highpass=f=200,lowpass=f=3000',  # Basic EQ to focus on voice frequencies
                        temp_mp3
                    ], check=True, capture_output=True)
                    
                    # Upload MP3 to Firebase
                    upload_audio_to_firebase(temp_mp3)
                    
                    # Clean up temporary files
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                    if os.path.exists(temp_mp3):
                        os.remove(temp_mp3)
                        
                except subprocess.CalledProcessError as e:
                    logging.error(f"FFmpeg conversion error: {e.stderr.decode()}")
                    messagebox.showerror("Conversion Error", "Failed to convert audio to MP3 format")
                except Exception as e:
                    logging.error(f"Error during audio processing: {e}")
                    messagebox.showerror("Processing Error", f"Failed to process audio: {e}")
                finally:
                    record_voice_btn.config(bg=BUTTON_BG, fg="white", text="Record Voice")

            recording_thread = threading.Thread(target=record_audio_stream, daemon=True)
            recording_thread.start()

        except Exception as e:
            logging.error(f"Error starting voice recording: {e}")
            messagebox.showerror("Recording Error", f"Failed to start recording: {e}")
            is_recording = False
            record_voice_btn.config(bg=BUTTON_BG, fg="white", text="Record Voice")
    else:
        # Stop recording when pressed again
        is_recording = False
        record_voice_btn.config(bg=BUTTON_BG, fg="white", text="Record Voice")

def upload_audio_to_firebase(local_path):
    """Upload audio file to Firebase Storage under voice_notes/"""
    try:
        # Create a unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}.mp3"
        
        logger.debug(f"Attempting to upload audio: {local_path}")
        
        # Create the blob with the correct path for audio files
        audio_blob = bucket.blob(f"voice_notes/{filename}")
        
        # Upload the file with content type
        audio_blob.upload_from_filename(
            local_path,
            content_type='audio/mp3'
        )
        
        # Make the file publicly accessible
        audio_blob.make_public()
        
        # Get the public URL
        public_url = audio_blob.public_url
        
        # Add metadata to Firestore
        db.collection('recordings').add({
            'name': filename,
            'url': public_url,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'type': 'audio'
        })
        
        messagebox.showinfo("Success", f"Audio uploaded successfully!")
        logger.info(f"Successfully uploaded {filename} to Firebase Storage")
        
    except Exception as e:
        logger.error(f"Upload Error: {e}")
        messagebox.showerror("Upload Error", f"Failed to upload audio: {str(e)}")

def firestore_listener_thread():
    doc_ref = db.collection('commands').document('record')
    last_state = False
    print("Listening for record commands in GUI...")
    while True:
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            if data.get('record', False) and not last_state:
                print("Remote recording requested!")
                start_recording()  # <-- This triggers your camera and upload
                # Reset Firestore trigger
                doc_ref.set({'record': False}, merge=True)
                last_state = True
            else:
                last_state = data.get('record', False)
        time.sleep(2)

# Create the main window and UI elements
root = tk.Tk()
root.title("Care Taker Bot")
root.geometry("1000x800")
root.minsize(800, 480)  # Minimum size for 7-inch display
root.configure(bg=STANDARD_BG)
root.resizable(True, True)

# --- TITLE & CLOCK ON SAME LINE ---
title_frame = tk.Frame(root, bg=STANDARD_BG)
title_frame.pack(fill='x', pady=(10, 0))
title_label = tk.Label(title_frame, text="CARE TAKER BOT", font=("DejaVu Sans", 32, "bold"), bg=STANDARD_BG, fg="#2C3E50")
title_label.pack(side='left', padx=(20, 0), anchor='w')
clock_label = tk.Label(title_frame, font=("DejaVu Sans Mono", 24), bg=STANDARD_BG, fg="#2C3E50")
clock_label.pack(side='right', padx=(0, 20), anchor='e')
update_clock()

# --- MAIN CONTENT FRAME (TWO COLUMNS, FLIPPED) ---
content_frame = tk.Frame(root, bg=STANDARD_BG)
content_frame.pack(fill='both', expand=True, padx=20, pady=10)
content_frame.grid_rowconfigure(0, weight=1)
content_frame.grid_columnconfigure(0, weight=1, minsize=250)  # Left: buttons
content_frame.grid_columnconfigure(1, weight=3, minsize=500)  # Right: interactive sections

# --- LEFT COLUMN: Profile, Emergency, Exit, Shutdown ---
left_col = tk.Frame(content_frame, bg=STANDARD_BG)
left_col.grid(row=0, column=0, sticky='ns', padx=(0, 20), pady=0)
left_col.grid_propagate(True)

# Profile & Greeting
profile_frame = tk.Frame(left_col, bg=STANDARD_BG)
profile_frame.pack(pady=5)
profile_label = tk.Label(profile_frame, bg=STANDARD_BG, width=80, height=80)
profile_label.pack()
greeting_label = tk.Label(left_col, text="", bg=STANDARD_BG, fg="#2C3E50", font=("DejaVu Sans", 12))
greeting_label.pack(pady=2)

# Emergency button (centered)
emergency_btn = create_small_button(left_col, "EMERGENCY", emergency_pressed, "#E74C3C", width=18)
emergency_btn.pack(pady=15, fill='x', expand=True)

# Exit GUI and Shutdown (stacked)
exit_btn = create_small_button(left_col, "Exit GUI", lambda: on_closing(), "#34495E", width=18)
exit_btn.pack(pady=5, fill='x', expand=True)
shutdown_btn = create_small_button(left_col, "Shutdown", shutdown_pi, "#555555", width=18)
shutdown_btn.pack(pady=5, fill='x', expand=True)

# --- RIGHT COLUMN: Camera, Task, Recordings (NO SECTION TITLES) ---
right_col = tk.Frame(content_frame, bg=STANDARD_BG)
right_col.grid(row=0, column=1, sticky='nsew')
right_col.grid_rowconfigure(0, weight=0)
right_col.grid_rowconfigure(1, weight=0)
right_col.grid_rowconfigure(2, weight=1)
right_col.grid_columnconfigure(0, weight=1)

# Camera controls (centered)
camera_row = tk.Frame(right_col, bg=STANDARD_BG)
camera_row.grid(row=0, column=0, pady=8, sticky='ew')
camera_row.grid_columnconfigure(0, weight=1)
camera_row.grid_columnconfigure(1, weight=1)
camera_btn = create_small_button(camera_row, "Open Camera View", show_camera, BUTTON_BG, width=16)
camera_btn.grid(row=0, column=0, padx=6, pady=8, sticky='e')
record_voice_btn = create_small_button(camera_row, "Record Voice", toggle_record_voice, BUTTON_BG, width=16)
record_voice_btn.grid(row=0, column=1, padx=6, pady=8, sticky='w')

# Task controls (centered)
task_row = tk.Frame(right_col, bg=STANDARD_BG)
task_row.grid(row=1, column=0, pady=8, sticky='ew')
task_row.grid_columnconfigure(0, weight=1)
task_display = tk.Label(task_row, text="Loading task...", font=("DejaVu Sans", 12), bg="white", fg="#2C3E50", wraplength=400, justify="center", relief="sunken", borderwidth=2, width=32, height=2)
task_display.pack(padx=8, pady=8, fill='x', expand=True)
task_btns = tk.Frame(task_row, bg=STANDARD_BG)
task_btns.pack(pady=2)
task_done_btn = create_small_button(task_btns, "Task Done", task_done, "#27AE60", width=10)
task_done_btn.pack(side='left', padx=3, fill='x', expand=True)
snooze_btn = create_small_button(task_btns, "Snooze", snooze_task, "#F39C12", fg_color="#222", width=10)
snooze_btn.pack(side='left', padx=3, fill='x', expand=True)

# Recordings controls (taller, scalable)
media_row = tk.Frame(right_col, bg=STANDARD_BG)
media_row.grid(row=2, column=0, padx=8, pady=8, sticky='nsew')
media_row.grid_rowconfigure(0, weight=1)
media_row.grid_columnconfigure(0, weight=1)
media_listbox = tk.Listbox(media_row, font=("DejaVu Sans", 12), width=40, height=7, bg="white", fg="#2C3E50", selectbackground=BUTTON_BG, selectforeground="white", relief="sunken", borderwidth=2)
media_listbox.grid(row=0, column=0, padx=8, pady=8, sticky='nsew')
media_btns = tk.Frame(media_row, bg=STANDARD_BG)
media_btns.grid(row=1, column=0, pady=2, sticky='ew')
play_btn = create_small_button(media_btns, "Play", lambda: play_recording(get_selected_recording()), BUTTON_BG, width=8)
play_btn.pack(side='left', padx=2, fill='x', expand=True)
pause_btn = create_small_button(media_btns, "Pause", pause_recording, BUTTON_BG, width=8)
pause_btn.config(state="disabled")
pause_btn.pack(side='left', padx=2, fill='x', expand=True)
resume_btn = create_small_button(media_btns, "Resume", resume_recording, BUTTON_BG, width=8)
resume_btn.config(state="disabled")
resume_btn.pack(side='left', padx=2, fill='x', expand=True)
stop_btn = create_small_button(media_btns, "Stop", stop_playback, BUTTON_BG, width=8)
stop_btn.config(state="disabled")
stop_btn.pack(side='left', padx=2, fill='x', expand=True)

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
        # Clean up temporary files
        cleanup_temp_files()
        # Destroy the window
        root.destroy()
    except Exception as e:
        logging.error(f"Error during shutdown: {e}")
        root.destroy()

root.protocol("WM_DELETE_WINDOW", on_closing)

# Start the Firestore listener thread
listener_thread = threading.Thread(target=firestore_listener_thread, daemon=True)
listener_thread.start()

root.mainloop()
