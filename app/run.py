from app import create_app

# Crear la instancia mediante la función Factory
app = create_app()

if __name__ == "__main__":
    # Iniciar el servidor WSGI de desarrollo
    app.run(host="0.0.0.0", port=5000, debug=True)