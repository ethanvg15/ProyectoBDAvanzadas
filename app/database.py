import pymongo
import redis

class Database:
    mongo_client = None
    mongo_db = None
    redis_client = None

    @classmethod
    def init_app(cls, app):
        # 1. Conexión a MongoDB Engine
        mongo_uri = app.config.get("MONGO_URI", "mongodb://localhost:27017/sistema_preventas")
        db_name = app.config.get("MONGO_DB_NAME", "sistema_preventas")
        
        cls.mongo_client = pymongo.MongoClient(mongo_uri)
        cls.mongo_db = cls.mongo_client[db_name]

        # 2. Conexión a Redis In-Memory Engine
        redis_host = app.config.get("REDIS_HOST", "localhost")
        redis_port = app.config.get("REDIS_PORT", 6380)
        
        cls.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            decode_responses=True
        )

def get_mongo_db():
    return Database.mongo_db

def get_redis_client():
    return Database.redis_client