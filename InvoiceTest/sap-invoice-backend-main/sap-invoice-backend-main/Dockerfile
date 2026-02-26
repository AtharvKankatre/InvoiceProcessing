# Cooper SAP Invoice Backend - Production Dockerfile
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=sap_invoice.settings

# Create working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt
RUN pip install psycopg["binary"]

# Copy project files
COPY . .

# Expose port
EXPOSE 8000

# Health check - Docker will restart container if this fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/sales/dashboard/ || exit 1

# Collect static files and start gunicorn
# NOTE: Migrations are NOT auto-run. Run them manually ONCE before first start:
#   docker exec cooper-backend python manage.py migrate
CMD ["sh", "-c", "\
    python manage.py collectstatic --noinput && \
    gunicorn sap_invoice.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120 --access-logfile - --error-logfile -"]

