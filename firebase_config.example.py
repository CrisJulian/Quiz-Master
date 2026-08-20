"""
Template for firebase_config.py.

To enable cloud sync:
  1. Copy this file to firebase_config.py (same folder as Quiz_Master.py)
  2. Fill in your own project's values below (Firebase console > Project
     settings > General > Your apps > Web app)
  3. Never commit firebase_config.py — it's already in .gitignore

Without this file, Quiz_Master.py runs fine in local-only mode.
"""

FIREBASE_CONFIG = {
    "apiKey": "YOUR_API_KEY",
    "authDomain": "YOUR_PROJECT.firebaseapp.com",
    "databaseURL": "https://YOUR_PROJECT-default-rtdb.firebaseio.com",
    "projectId": "YOUR_PROJECT",
    "storageBucket": "YOUR_PROJECT.firebasestorage.app",
    "appId": "YOUR_APP_ID",
}
