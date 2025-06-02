# major_project_app

MajorProjectApp is a hybrid system combining a Flutter-based mobile app and a Raspberry Pi-powered desktop interface designed to assist with daily task management, voice communication, and emergency monitoring — especially useful for caretakers and elderly support scenarios.

This system bridges real-time interaction between a mobile user and a Raspberry Pi-based GUI using Firebase cloud services.

## Key Features

Mobile Application (Flutter based) --->
1.Voice Note Recording – Easily record, upload, and playback voice notes stored securely in Firebase Storage.
2.Task Management – View, track, and mark daily tasks with smart reminders.
3.User Profiles – Personalized greeting and profile-based access via Firebase Authentication.
4. Emergency Notifications – Instantly receive alerts triggered from the Raspberry Pi interface.
5. Remote Monitoring – View emergency camera feed activated from the Pi GUI.
6. Two-Way Communication – Receive voice messages sent directly from the Raspberry Pi GUI

 Raspberry Pi based GUI --->
1. Touchscreen Interface – Clean and intuitive Tkinter-based GUI with user profile, real-time clock, and playback controls.
2. Emergency Trigger – One-tap emergency button that alerts the user and shares a live camera view.
3. Camera Access – Allows the local user to view themselves on screen or send live feed on emergency.
4. Voice Messaging – Local user can record voice responses that sync back to the mobile app.
5. Firebase Integration – Syncs tasks, voice notes, and messages with the cloud for seamless data sharing.

TechStack --->
Frontend: Flutter (Mobile App)
Backend/Sync: Firebase (Firestore, Storage, Auth)
Raspberry Pi: Python (Tkinter GUI), Camera Module, USB Audio Devices
Deployment: Raspberry Pi OS with touch display
