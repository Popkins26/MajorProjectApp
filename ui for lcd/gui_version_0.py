import tkinter as tk
from tkinter import messagebox
import datetime
import os
import cv2
import sounddevice as sd
from scipy.io.wavfile import write
import time
import threading
import numpy as np
import firebase_admin
from firebase_admin import credentials, storage, firestore
import logging
import pygame  # Added for audio playback
from datetime import datetime
from tkinter import ttk

# Initialize pygame mixer for audio playback
pygame.mixer.init()

# Firebase Initialization
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
       'storageBucket': 'project-app-8f1c2.firebasestorage.app'  # ✅ Correct bucket name
})
bucket = storage.bucket()
db = firestore.client()

# Global variables
user_name = "User"
user_profile_pic_url = None
current_task = "Take medicine"
task_sent_time = "9:00 AM, April 12"
task_due_time = "10:00 AM, April 12"

# Recording state
is_recording = False
recording_thread = None
recording_buffer = []

# Logging setup
logging.basicConfig(level=logging.DEBUG)

def fetch_user_data():
    global user_name, user_profile_pic_url
    try:
        user_doc = db.collection('users').document('user_id').get()  # Replace 'user_id' with actual user ID
        if user_doc.exists:
            user_data = user_doc.to_dict()
            user_name = user_data.get('name', 'User')
            user_profile_pic_url = user_data.get('profileImageUrl', None)
        else:
            print("User document does not exist.")
    except Exception as e:
        print(f"Error fetching user data: {e}")

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
    messagebox.showwarning("Emergency", "Emergency alert sent!")

def shutdown_pi():
    confirm = messagebox.askyesno("Shutdown", "Are you sure you want to shut down the Raspberry Pi?")
    if confirm:
        os.system("sudo shutdown now")

def toggle_record_voice():
    global is_recording
    if is_recording:
        stop_recording()
    else:
        start_recording()

def start_recording():
    global is_recording, recording_thread, recording_buffer
    is_recording = True
    recording_buffer = []
    record_voice_btn.config(bg="red", text="⏹️")
    logging.debug("Recording started.")

    def record_audio():
        fs = 16000  # Reduced sample rate for compression
        channels = 1
        try:
            with sd.InputStream(samplerate=fs, channels=channels, dtype='float32', callback=audio_callback):
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

from pydub import AudioSegment  # Add at the top of your file

def stop_recording():
    global is_recording, recording_thread, recording_buffer
    is_recording = False
    record_voice_btn.config(bg="#6A994E", text="🎤")

    if recording_thread and recording_thread.is_alive():
        recording_thread.join()
        logging.debug("Recording thread stopped.")

    if recording_buffer:
        fs = 16000
        filename_wav = f"voice_note_{int(time.time())}.wav"
        filename_mp3 = filename_wav.replace(".wav", ".mp3")

        audio_data = np.concatenate(recording_buffer, axis=0)
        audio_data_int16 = np.int16(audio_data * 32767)

        write(filename_wav, fs, audio_data_int16)

        # Convert WAV to real MP3 using pydub
        try:
            sound = AudioSegment.from_wav(filename_wav)
            sound.export(filename_mp3, format="mp3")
            os.remove(filename_wav)  # Clean up the WAV file
            messagebox.showinfo("Saved", f"Voice note saved as {filename_mp3}. Uploading to Firebase...")
            upload_to_firebase(filename_mp3)
        except Exception as e:
            messagebox.showerror("Conversion Error", f"Failed to convert to MP3: {e}")
            logging.error(f"MP3 Conversion Error: {e}")


    global is_recording, recording_thread, recording_buffer
    is_recording = False
    record_voice_btn.config(bg="#6A994E", text="🎤")

    if recording_thread and recording_thread.is_alive():
        recording_thread.join()
        logging.debug("Recording thread stopped.")

    if recording_buffer:
        fs = 16000  # Same reduced sample rate
        filename = f"voice_note_{int(time.time())}.mp3"
        audio_data = np.concatenate(recording_buffer, axis=0)

        # Convert float32 to int16 for smaller file size
        audio_data_int16 = np.int16(audio_data * 32767)

        write(filename, fs, audio_data_int16)
        messagebox.showinfo("Saved", f"Voice note saved as {filename}. Uploading to Firebase...")
        upload_to_firebase(filename)

def upload_to_firebase(local_path):
    try:
        blob = bucket.blob(f"voice_notes/{os.path.basename(local_path)}")
        blob.upload_from_filename(local_path)
        os.remove(local_path)  # Clean up local storage
        messagebox.showinfo("Uploaded", f"Uploaded {os.path.basename(local_path)} to Firebase Storage.")
    except Exception as e:
        messagebox.showerror("Upload Error", f"Failed to upload: {e}")
        logging.error(f"Upload Error: {e}")

def show_camera():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        messagebox.showerror("Camera Error", "Cannot open camera")
        return

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        cv2.imshow('Live Camera Feed - Press Q to Exit', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

def task_done():
    global current_task, task_sent_time, task_due_time
    if current_task:
        messagebox.showinfo("Task Done", "Task marked as done and updated to the app.")
        task_display.config(text="No current task.")
        current_task = None
        task_sent_time = None
        task_due_time = None
    else:
        messagebox.showinfo("No Task", "No task to mark as done.")

def add_new_task(task, sent_time, due_time):
    global current_task, task_sent_time, task_due_time
    current_task = task
    task_sent_time = sent_time
    task_due_time = due_time
    task_text = f"Task: {current_task}\nSent: {task_sent_time}"
    if task_due_time:
        task_text += f"\nDue: {task_due_time}"
    task_display.config(text=task_text)

# Media player functions
def fetch_recordings():
    """Fetch the list of recordings from Firebase Storage."""
    try:
        blobs = bucket.list_blobs(prefix="recordings/")
        recordings = [blob.name.split("/")[-1] for blob in blobs if blob.name.endswith(".mp3")]
        logging.debug(f"Fetched recordings: {recordings}")
        return recordings
    except Exception as e:
        logging.error(f"Error fetching recordings: {e}")
        return []

def play_recording(file_name):
    """Download and play a recording from Firebase."""
    try:
        import tempfile

        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_path = temp_file.name
        temp_file.close()

        # Download from Firebase
        blob = bucket.blob(f"recordings/{file_name}")
        blob.download_to_filename(temp_path)

        # Play the file using pygame
        pygame.mixer.music.load(temp_path)
        pygame.mixer.music.play()

        def remove_temp_after_playback():
            while pygame.mixer.music.get_busy():
                time.sleep(0.5)
            pygame.mixer.music.unload()  # ✅ Release the file
            os.remove(temp_path)         # ✅ Now it's safe to delete

        threading.Thread(target=remove_temp_after_playback, daemon=True).start()

    except Exception as e:
        messagebox.showerror("Playback Error", f"Failed to play recording: {e}")
        logging.error(f"Playback Error: {e}")

def pause_recording():
    """Pause the currently playing recording."""
    pygame.mixer.music.pause()

def resume_recording():
    """Resume the paused recording."""
    pygame.mixer.music.unpause()

def stop_recording_playback():
    """Stop the currently playing recording."""
    pygame.mixer.music.stop()

def update_media_player():
    """Update the media player with the list of recordings."""
    recordings = fetch_recordings()
    if recordings:
        media_listbox.delete(0, tk.END)
        for recording in recordings:
            media_listbox.insert(tk.END, recording)
    else:
        media_listbox.insert(tk.END, "No recordings available.")

fetch_user_data()

root = tk.Tk()
root.title("Care Taker Bot")
root.geometry("800x480")
root.configure(bg="#EDF1E1")

tk.Label(root, text="CARE TAKER BOT", font=("Arial", 28, "bold"), bg="#EDF1E1", fg="#333").pack(pady=10)

left_frame = tk.Frame(root, bg="#EDF1E1")
left_frame.place(x=20, y=60)

# Display user profile picture
if user_profile_pic_url:
    try:
        from urllib.request import urlopen
        from PIL import Image, ImageTk
        import io
        image_bytes = urlopen(user_profile_pic_url).read()
        image = Image.open(io.BytesIO(image_bytes))
        image = image.resize((100, 100), Image.ANTIALIAS)
        user_photo = ImageTk.PhotoImage(image)
        tk.Label(left_frame, image=user_photo, bg="#EDF1E1").pack(pady=5)
    except Exception as e:
        print(f"Error loading profile picture: {e}")
else:
    tk.Label(left_frame, text="No Profile Picture", bg="#EDF1E1", font=("Arial", 10), relief="solid", width=20, height=6, borderwidth=2).pack(pady=5)

greeting_label = tk.Label(left_frame, text="", bg="#EDF1E1", fg="#333", wraplength=150, justify="center", font=("Arial", 12))
greeting_label.pack(pady=5)

tk.Button(left_frame, text="Emergency", command=emergency_pressed, bg="#D9534F", fg="white", font=("Arial", 12), width=20, height=2, relief="flat").pack(pady=5)
tk.Button(left_frame, text="Shutdown Pi", command=shutdown_pi, bg="#555", fg="white", font=("Arial", 12), width=20, height=2, relief="flat").pack(pady=5)

box_width = 40
box_height = 4

camera_frame = tk.Frame(root, bg="#EDF1E1")
camera_frame.place(x=230, y=70)

camera_btn = tk.Button(camera_frame, text="📷 Open Camera View", command=show_camera, font=("Arial", 14), bg="#6A994E", fg="white", width=box_width, height=box_height, relief="flat")
camera_btn.grid(row=0, column=0, padx=10)

record_voice_btn = tk.Button(camera_frame, text="🎤", command=toggle_record_voice, bg="#6A994E", fg="white", font=("Arial", 14), width=2, height=1, relief="flat")
record_voice_btn.grid(row=0, column=1, padx=10)

task_frame = tk.Frame(root, bg="#EDF1E1")
task_frame.place(x=230, y=200)

task_display = tk.Label(task_frame, text=f"Task: {current_task}\nSent: {task_sent_time}\nDue: {task_due_time}", font=("Arial", 12), bg="#EDF1E1", fg="#333", wraplength=500, justify="center", relief="solid", width=box_width, height=box_height)
task_display.grid(row=0, column=0, padx=10)

task_done_btn = tk.Button(task_frame, text="✅", command=task_done, bg="#6A994E", fg="white", font=("Arial", 14), width=2, height=1, relief="flat")
task_done_btn.grid(row=0, column=1, padx=10)

# Media player frame
media_frame = tk.Frame(root, bg="#EDF1E1")
media_frame.place(x=230, y=330)

media_listbox = tk.Listbox(media_frame, font=("Arial", 12), width=box_width, height=box_height, bg="#EDF1E1", fg="#333")
media_listbox.grid(row=0, column=0, padx=10)

play_btn = tk.Button(media_frame, text="▶️ Play", command=lambda: play_recording(media_listbox.get(tk.ACTIVE)), bg="#6A994E", fg="white", font=("Arial", 14), width=10, height=1, relief="flat")
play_btn.grid(row=0, column=1, padx=5)

pause_btn = tk.Button(media_frame, text="⏸️ Pause", command=pause_recording, bg="#6A994E", fg="white", font=("Arial", 14), width=10, height=1, relief="flat")
pause_btn.grid(row=1, column=1, padx=5)

resume_btn = tk.Button(media_frame, text="🔁 Resume", command=resume_recording, bg="#6A994E", fg="white", font=("Arial", 14), width=10, height=1, relief="flat")
resume_btn.grid(row=0, column=2, padx=5)

update_media_player()

add_new_task("Take medicine", "9:00 AM, April 12", "10:00 AM, April 12")

root.mainloop()