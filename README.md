# Preventas NoSQL

Aplicación web para vender entradas en preventa por tiempo limitado.
Proyecto #1 de TI4601 Bases de datos avanzadas (II semestre 2026).

- **Aplicación web:** Python 3.12 + Flask
- **MongoDB:** catálogo de eventos y registro de las entradas obtenidas
- **Redis:** preventas abiertas, con sus entradas disponibles y su tiempo de vida (TTL)

## Cómo ejecutarlo

Requiere Docker Desktop abierto.

```bash
docker compose up --build
```

| Qué | Dirección |
| --- | --- |
| Aplicación | http://localhost:5000 |
| Mongo Express (usuario `admin`, clave `pass`) | http://localhost:8081 |
| Redis desde la terminal | `docker exec -it redis-preventas redis-cli` |

Para apagar: `Ctrl + C`, y luego `docker compose down`
(con `-v` se borran también los datos de MongoDB).

## Funcionalidades

| # | Funcionalidad | Ruta | Archivo |
| --- | --- | --- | --- |
| 1 | Carga inicial del JSON a MongoDB | `/eventos/cargar` | `app/blue_prints/eventos/routes.py` |
| 2 | Abrir una preventa | `/preventas/abrir` | `app/blue_prints/preventas/routes.py` |
| 3 | Preventas abiertas | `/preventas/activas` | `app/blue_prints/preventas/routes.py`, `app/preventas_servicio.py` |
| 4 | Obtener una entrada | `/entradas/obtener` | `app/blue_prints/entradas/routes.py` |
| 5 | Consultar entradas por categoría | `/entradas/consulta` | `app/blue_prints/entradas/routes.py` |

## Modelo de datos

### MongoDB (base `sistema_preventas`)

| Colección | Contenido |
| --- | --- |
| `eventos` | El catálogo tal como viene en el JSON (`id`, `nombre`, `categoria`, `precio` y los atributos propios de cada categoría). No se modifica al abrir preventas. |
| `entradas` | Una entrada por documento: `codigo`, `nombre_cliente`, `nombre_evento`, `categoria`, `fecha_hora`, más `id_evento` y `cliente_clave` (el nombre en minúsculas, para comparar clientes). |
| `contadores` | Un contador por evento, para generar el consecutivo del código (`E001-0001`). |

Índices únicos en `entradas`: `(cliente_clave, id_evento)` (un cliente, una entrada por evento) y `codigo`.

### Redis

Una llave por preventa abierta:

```
preventa:<id del evento>   ->   entradas disponibles (número)      TTL = duración de la preventa
```

Ejemplo: `preventa:E001` con valor `5` y TTL de 1800 segundos.

- **Vencimiento:** lo gestiona el TTL de Redis; al vencer, la llave desaparece sola.
- **Una sola preventa por evento:** se crea con `SET ... NX EX`, en una sola operación atómica.
- **Agotada:** la llave queda con valor `0` hasta que venza, para poder distinguir "agotada" de "vencida".

## Cómo se entrega una entrada

1. Si la llave `preventa:<id>` no existe en Redis, la preventa **venció**.
2. Si el cliente ya tiene una entrada de ese evento en MongoDB, se rechaza como **duplicada**.
3. Un script Lua en Redis descuenta una entrada de forma atómica, solo si quedan: así dos clientes
   simultáneos no pueden llevarse la última. Si no quedan, la preventa está **agotada**.
4. Se genera el código y se guarda la entrada en MongoDB. Si este paso falla, la entrada se
   devuelve a Redis (solo si la preventa sigue viva, para no recrear una llave sin TTL).

## Estructura

```
app/
  __init__.py              crea la app y registra los módulos
  config.py, database.py   configuración y conexión a MongoDB y Redis
  preventas_servicio.py    lee de Redis las preventas vigentes (funcionalidades 3 y 4)
  utils.py                 utilidades compartidas
  blue_prints/
    eventos/               catálogo y carga inicial
    preventas/             abrir preventa y preventas abiertas
    entradas/              obtener entrada y consulta por categoría
  templates/               páginas HTML (Bootstrap)
docker-compose.yml         app + MongoDB + Redis + Mongo Express
Dockerfile
```
