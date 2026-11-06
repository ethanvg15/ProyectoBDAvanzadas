from flask import Flask, redirect, url_for
from app.config import Config
from app.database import Database

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializar conectores de MongoDB y Redis
    Database.init_app(app)

    # Registrar el Blueprint del módulo de eventos
    from app.blue_prints.eventos.routes import eventos_bp
    app.register_blueprint(eventos_bp, url_prefix="/eventos")

    # Ruta raíz principal del sitio web
    @app.route("/")
    def root():
        return redirect(url_for("eventos.ver_catalogo"))

    return app