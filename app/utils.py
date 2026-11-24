def id_de_evento(evento):
    """Devuelve el identificador del evento tal como viene en el JSON (campo 'id').
    Si el documento no trae 'id', usa el _id interno de Mongo como respaldo."""
    return str(evento.get("id", evento["_id"]))
