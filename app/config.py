import os
from dotenv import load_dotenv

load_dotenv()

# Determine base directory of the project
BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")

# Ensure the instance directory exists
os.makedirs(INSTANCE_DIR, exist_ok=True)

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "cambiame")
    
    # 🔧 FORZAR LA RUTA CORRECTA
    SQLALCHEMY_DATABASE_URI = 'sqlite:////app/instance/database.db'
    
    # Para desarrollo local, usar la variable de entorno
    # SQLALCHEMY_DATABASE_URI = os.getenv(
    #     "DATABASE_URL",
    #     "sqlite:///" + os.path.join(INSTANCE_DIR, "database.db")
    # )
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
    GOOGLE_SERVICE_ACCOUNT_EMAIL = os.getenv("GOOGLE_SERVICE_ACCOUNT_EMAIL")
    GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY")