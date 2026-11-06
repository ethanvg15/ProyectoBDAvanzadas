#¿Qué es? Clase que encapsula la carga de variables desde el archivo .env hacia el objeto de configuración nativo de Flask.
import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "llave_secreta_desarrollo")
    
    # Configuración de MongoDB
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/sistema_preventas")
    
    # Configuración de Redis
    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", 6380))
