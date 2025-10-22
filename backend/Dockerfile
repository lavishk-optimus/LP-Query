FROM python:3.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .

# Install prerequisites
RUN apt-get update && apt-get install -y curl gnupg2 ca-certificates
 
# Add Microsoft repository for SQL Server ODBC Driver (modern approach)
RUN curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg
RUN echo "deb [arch=amd64,armhf,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/ubuntu/20.04/prod focal main" > /etc/apt/sources.list.d/mssql-release.list
 
# Install ODBC Driver 17 for SQL Server
RUN apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 unixodbc-dev
 
# Clean up to reduce image size
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]