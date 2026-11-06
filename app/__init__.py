from flask import Flask
from app.config import Config
from app.database import Database

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializar conectores de bases de datos NoSQL
    Database.init_app(app)

    # Registrar Blueprints
    from app.blue_prints.eventos.routes import eventos_bp
    app.register_blueprint(eventos_bp, url_prefix="/eventos")

    return app