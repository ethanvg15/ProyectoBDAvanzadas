from flask import Flask
from app.config import Config
from app.database import Database

def create_app():
    """Función de fábrica para instanciar la aplicación web Flask."""
    app = Flask(__name__)
    
    # Cargar configuraciones
    app.config.from_object(Config)

    # Inicializar conectores de bases de datos
    Database.init_app(app)

    # Registrar Blueprints (Módulos de rutas)
    from app.blue_prints.eventos.routes import eventos_bp
    from app.blue_prints.preventas.routes import preventas_bp
    from app.blue_prints.entradas.routes import entradas_bp

    app.register_blueprint(eventos_bp, url_prefix="/eventos")
    app.register_blueprint(preventas_bp, url_prefix="/preventas")
    app.register_blueprint(entradas_bp, url_prefix="/entradas")

    return app