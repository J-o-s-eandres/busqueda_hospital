FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# 🔧 CREAR DIRECTORIO DE INSTANCIA DURANTE EL BUILD
RUN mkdir -p /app/instance && \
    chmod -R 777 /app/instance && \
    echo "✅ Directorio /app/instance creado en el build"

# Verificar que existe
RUN ls -la /app/ && ls -la /app/instance/

# Dar permisos al entrypoint
RUN chmod +x entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["./entrypoint.sh"]