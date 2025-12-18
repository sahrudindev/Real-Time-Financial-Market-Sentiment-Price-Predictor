# Custom MLflow Dockerfile with PostgreSQL support
FROM ghcr.io/mlflow/mlflow:v2.17.2

# Install psycopg2 for PostgreSQL backend and boto3 for S3/MinIO
RUN pip install --no-cache-dir psycopg2-binary boto3

# Expose MLflow port
EXPOSE 5000
