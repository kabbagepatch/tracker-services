import firebase_admin
from firebase_admin import credentials

from dependencies.config import get_settings


def init_firebase():
    if not firebase_admin._apps:
        settings = get_settings()
        if settings.google_application_credentials:
            cred_path = settings.google_application_credentials.get_secret_value()
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
        print("Current App Name:", firebase_admin.get_app().project_id)
