from flask import Blueprint, render_template, request, redirect, url_for, flash
from app.database import get_mongo_db
import json

eventos_bp = Blueprint("eventos", __name__)

@eventos_bp.route("/cargar", methods=["GET", "POST"])
def cargar_inicial():
    if request.method == "POST":
        file = request.files.get("archivo_json")
        if not file or file.filename == "":
            flash("Debe seleccionar un archivo JSON válido.", "error")
            return redirect(request.url)

        try:
            db = get_mongo_db()
            datos = json.load(file)
            
            # Limpiar colección previa o insertar directamente (Requerimiento 1)
            if isinstance(datos, list) and len(datos) > 0:
                db.eventos.delete_many({}) # Limpia la colección inicial si estaba vacía
                db.eventos.insert_many(datos)
                flash(f"Se cargaron {len(datos)} eventos exitosamente en MongoDB.", "success")
            else:
                flash("El archivo JSON no contiene un formato de lista válido.", "error")
        except Exception as e:
            flash(f"Error al procesar el archivo: {str(e)}", "error")

        return redirect(url_for("eventos.cargar_inicial"))

    return render_template("eventos/cargar.html")