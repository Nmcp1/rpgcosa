# Imagen base
FROM python:3.11-slim

# No generar .pyc y logs sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Dependencias de sistema mínimas (por si luego agregas más cosas)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiamos requirements e instalamos dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el proyecto
COPY . .

# Collectstatic para servir /static/ con DEBUG = False
RUN python manage.py collectstatic --noinput

# Puerto donde escucha la app
EXPOSE 8000

# Comando de arranque:
# 1) aplica migraciones
# 2) levanta gunicorn
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn noteboard.wsgi:application --bind 0.0.0.0:8000"]
