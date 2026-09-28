import os
import firebase_admin
from firebase_admin import credentials

def init_firebase():
  if not firebase_admin._apps:
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not cred_path:
      raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is not set")
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
    print("Current App Name:", firebase_admin.get_app().project_id)
