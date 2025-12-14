# Imagen base
FROM python:3.11-slim

# No generar .pyc y logs sin buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Dependencias de sistema mínimas (para compilar wheels si hiciera falta)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalación de dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el proyecto
COPY . .

# Puerto donde escucha la app
EXPOSE 8000

# Arranque:
# 1) migraciones
# 2) collectstatic (en runtime, no en build)
# 3) gunicorn
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn rpgloco.wsgi:application --bind 0.0.0.0:8000"]
