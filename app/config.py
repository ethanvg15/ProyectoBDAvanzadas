#¿Qué es? Clase que encapsula la carga de variables desde el archivo .env hacia el objeto de configuración nativo de Flask.
import os
from dotenv import load_dotenv

# Cargar el archivo .env ubicado en la raíz
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_fallback_key")
    MONGO_URI = os.getenv("MONGO_URI")
    MONGO_DB_NAME = os.getenv("MONGO_DB_NAME")
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))