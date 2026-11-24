import os

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "llave_secreta_preventas_2026")
    
    # Nombre de la base de datos documental en MongoDB
    MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "sistema_preventas")
    
    # Enlaces de conexión adaptativos (Red interna de Docker por defecto)
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo-preventas:27017/sistema_preventas")
    REDIS_HOST = os.environ.get("REDIS_HOST", "redis-preventas")
    REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))