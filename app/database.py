import redis
from pymongo import MongoClient

class Database:
    mongo_client = None
    mongo_db = None
    redis_client = None

    @classmethod
    def init_app(cls, app):
        """Inicializa los clientes de base de datos usando la configuración de Flask."""
        # Conexión a MongoDB (Driver Oficial PyMongo)
        cls.mongo_client = MongoClient(app.config["MONGO_URI"])
        cls.mongo_db = cls.mongo_client[app.config["MONGO_DB_NAME"]]

        # Conexión a Redis (Driver Oficial Redis-Py)
        cls.redis_client = redis.Redis(
            host=app.config["REDIS_HOST"],
            port=app.config["REDIS_PORT"],
            db=app.config["REDIS_DB"],
            decode_responses=True # Convierte las respuestas binarias de Redis a cadenas str de Python
        )

def get_mongo_db():
    """Retorna la instancia de la base de datos de MongoDB."""
    return Database.mongo_db

def get_redis_client():
    """Retorna la instancia del cliente de Redis."""
    return Database.redis_client