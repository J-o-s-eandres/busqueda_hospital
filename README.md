# Busqueda Hospitalar

Este proyecto es una aplicación Flask para buscar y gestionar información hospitalaria.

## Requisitos
- Python 3.12 (o 3.11)
- pip
- virtualenv (recomendado)
- Docker (opcional, para despliegue con docker-compose)

## Instalación local
`ash
# Clonar el repositorio (si procede)
git clone <repo-url>
cd busqueda_hostipal

# Crear entorno virtual
python -m venv venv
./venv/Scripts/activate  # en PowerShell

# Instalar dependencias
pip install -r requirements.txt

# Inicializar la base de datos
flask db init
flask db migrate -m  Initial migration
flask db upgrade
`

## Ejecutar la aplicación
`ash
flask run --host=0.0.0.0 --port=5000
`
Visita http://localhost:5000 en tu navegador.

## Docker
`ash
docker compose up --build
`
El contenedor expondrá el puerto 5000.

## Funcionalidades principales
- **Búsqueda pública**: página  /public/search  muestra resultados con columnas: nombre, hospital, teléfono, familiar, etc.
- **Admin panel**: CRUD de usuarios y personas, exportación CSV desde el dashboard.
- **Sincronización con Google Sheets** (pendiente de configuración de credenciales).

## Tests
`ash
pytest
`

## Licencia
MIT
