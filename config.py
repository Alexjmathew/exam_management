import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    FIREBASE_CONFIG = 'firebase_config.json'
