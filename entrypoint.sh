#!/bin/bash
set -e

echo "🔄 Iniciando contenedor..."

# Crear directorio
echo "📁 Creando directorio /app/instance..."
mkdir -p /app/instance
chmod -R 777 /app/instance

if [ -d "/app/instance" ] && [ -w "/app/instance" ]; then
    echo "✅ Directorio /app/instance creado y escribible"
    ls -la /app/ | grep instance
else
    echo "❌ ERROR: /app/instance NO es accesible"
    exit 1
fi

echo "📊 Inicializando base de datos..."
python3 << 'EOF'
import os
import sys

# Verificar directorio
if not os.path.exists("/app/instance"):
    print("❌ ERROR: /app/instance no existe")
    sys.exit(1)

from app import create_app, db
from app.models import seed_estatuses

app = create_app()
with app.app_context():
    # 🔧 FORZAR LA RUTA CORRECTA
    db_path = '/app/instance/database.db'
    print(f'📁 Ruta de la base de datos: {db_path}')
    
    # Verificar que la URL es correcta
    print(f'📁 URL de la DB: {db.engine.url}')
    
    print('🔄 Creando tablas...')
    db.create_all()
    print('✅ Tablas creadas')
    
    print('🌱 Sembrando estatus...')
    seed_estatuses()
    print('✅ Estatus sembrados')
    
    from app.models import Estatus
    count = Estatus.query.count()
    print(f'📊 {count} estatus en la base de datos')
    
    if os.path.exists(db_path):
        print(f'✅ Base de datos: {db_path}')
        print(f'📊 Tamaño: {os.path.getsize(db_path)} bytes')
    else:
        print(f'⚠️  No se encontró {db_path}')
EOF

echo "🚀 Iniciando Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 --workers 2 run:app