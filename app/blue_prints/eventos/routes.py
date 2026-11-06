from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_mongo_db
import json

# Definición del Blueprint para el módulo de eventos
eventos_bp = Blueprint("eventos", __name__)

@eventos_bp.route("/cargar", methods=["GET", "POST"])
def cargar_inicial():
    """
    Rubro 1: Carga inicial de datos desde un archivo JSON hacia MongoDB (10 pts).
    """
    if request.method == "POST":
        # Recibir el archivo adjunto desde el formulario HTML
        file = request.files.get("archivo_json")
        
        # Validar la presencia del archivo
        if not file or file.filename == "":
            flash("Debe seleccionar un archivo JSON válido.", "error")
            return redirect(request.url)

        try:
            db = get_mongo_db()
            
            # Cargar y parsear el contenido JSON a objetos nativos de Python
            contenido = json.load(file)

            if isinstance(contenido, list) and len(contenido) > 0:
                # Se vacía la colección 'eventos' para asegurar una carga inicial limpia
                db.eventos.delete_many({})
                
                # Inserción masiva de los documentos en la colección de MongoDB
                db.eventos.insert_many(contenido)
                
                flash(f"¡Carga exitosa! Se procesaron e insertaron {len(contenido)} eventos en MongoDB.", "success")
            else:
                flash("El archivo JSON debe contener una lista de eventos válida.", "error")

        except Exception as e:
            flash(f"Ocurrió un error al procesar el archivo: {str(e)}", "error")

        return redirect(url_for("eventos.cargar_inicial"))

    # Renderizar la plantilla gráfica para la carga
    return render_template("eventos/cargar.html")