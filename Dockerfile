FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (helpful for scientific Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py ./app.py
COPY projects_data ./projects_data

# Create reference_files directory for NAS mounting
RUN mkdir -p reference_files

# Streamlit config: listen on all interfaces, port 8501 (default)
EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]


