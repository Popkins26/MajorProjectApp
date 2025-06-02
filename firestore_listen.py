import firebase_admin
from firebase_admin import credentials, firestore
import subprocess
import time

cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

def listen_for_record_command():
    doc_ref = db.collection('commands').document('record')
    last_state = False
    print("Listening for record commands...")
    while True:
        doc = doc_ref.get()
        if doc.exists:
            data = doc.to_dict()
            if data.get('record', False) and not last_state:
                print("Recording requested!")
                # Start camera_server.py (Flask server)
                flask_proc = subprocess.Popen(['python3', 'camera_server.py', '--record'])
                # Wait for recording to finish (adjust as needed)
                time.sleep(15)
                flask_proc.terminate()
                # Reset Firestore trigger
                doc_ref.set({'record': False}, merge=True)
                last_state = True
            else:
                last_state = data.get('record', False)
        time.sleep(2)

if __name__ == "__main__":
    listen_for_record_command()