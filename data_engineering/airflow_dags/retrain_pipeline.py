"""
Automated Retraining Pipeline DAG
=================================
Daily DAG that checks for new data, runs transformations, 
retrains the model, and promotes to Production if better.

Schedule: Daily at 2 AM UTC
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sensors.sql import SqlSensor
from airflow.utils.trigger_rule import TriggerRule
import mlflow
from mlflow.tracking import MlflowClient
import logging

# =============================================================================
# Configuration
# =============================================================================

POSTGRES_CONN_ID = "postgres_default"
MLFLOW_TRACKING_URI = "http://mlflow:5000"
MODEL_NAME = "crypto-price-predictor"
DBT_PROJECT_DIR = "/opt/airflow/dbt"

default_args = {
    "owner": "mlops",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# =============================================================================
# Task Functions
# =============================================================================

def check_data_freshness(**context):
    """Check if new data has arrived in the last 24 hours."""
    hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
    
    query = """
    SELECT COUNT(*) as new_records
    FROM warehouse.raw_market_data
    WHERE ingested_at >= NOW() - INTERVAL '24 hours'
    """
    
    result = hook.get_first(query)
    new_records = result[0] if result else 0
    
    logging.info(f"New records in last 24h: {new_records}")
    
    # Store for downstream tasks
    context["ti"].xcom_push(key="new_records", value=new_records)
    
    # Need at least 100 new records to retrain
    if new_records >= 100:
        return "run_dbt_transformations"
    else:
        return "skip_retraining"


def skip_retraining_task(**context):
    """Log skip reason."""
    new_records = context["ti"].xcom_pull(key="new_records", task_ids="check_data_freshness")
    logging.info(f"Skipping retraining: only {new_records} new records (need 100+)")


def run_training(**context):
    """Execute the training script and capture results."""
    import subprocess
    import json
    
    # Run training script
    result = subprocess.run(
        ["python", "/opt/airflow/data_science/src/models/train_model.py"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        logging.error(f"Training failed: {result.stderr}")
        raise Exception(f"Training failed: {result.stderr}")
    
    logging.info(f"Training output: {result.stdout}")
    
    # Get the latest run from MLflow
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()
    
    experiment = client.get_experiment_by_name("crypto-price-predictor")
    if experiment:
        runs = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            order_by=["start_time DESC"],
            max_results=1
        )
        
        if runs:
            latest_run = runs[0]
            context["ti"].xcom_push(key="run_id", value=latest_run.info.run_id)
            context["ti"].xcom_push(
                key="test_rmse", 
                value=latest_run.data.metrics.get("test_rmse", float("inf"))
            )
            logging.info(f"Training completed. Run ID: {latest_run.info.run_id}")


def evaluate_and_promote(**context):
    """
    Compare new model with current Production model.
    Promote to Production if new model is better.
    """
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    client = MlflowClient()
    
    # Get new model metrics
    new_run_id = context["ti"].xcom_pull(key="run_id", task_ids="train_model")
    new_rmse = context["ti"].xcom_pull(key="test_rmse", task_ids="train_model")
    
    if new_rmse is None:
        logging.warning("No new model metrics found. Skipping promotion.")
        return
    
    logging.info(f"New model RMSE: {new_rmse}")
    
    # Get current Production model metrics
    current_rmse = float("inf")
    try:
        versions = client.get_latest_versions(MODEL_NAME, stages=["Production"])
        if versions:
            prod_version = versions[0]
            prod_run = client.get_run(prod_version.run_id)
            current_rmse = prod_run.data.metrics.get("test_rmse", float("inf"))
            logging.info(f"Current Production RMSE: {current_rmse}")
    except Exception as e:
        logging.warning(f"No Production model found: {e}")
    
    # Compare and promote if better
    improvement_threshold = 0.01  # 1% improvement required
    
    if new_rmse < current_rmse * (1 - improvement_threshold):
        # Find the new model version
        versions = client.search_model_versions(f"name='{MODEL_NAME}'")
        new_versions = [v for v in versions if v.run_id == new_run_id]
        
        if new_versions:
            new_version = new_versions[0]
            
            # Transition old Production to Archived
            try:
                old_prod = client.get_latest_versions(MODEL_NAME, stages=["Production"])
                for v in old_prod:
                    client.transition_model_version_stage(
                        name=MODEL_NAME,
                        version=v.version,
                        stage="Archived"
                    )
            except Exception:
                pass
            
            # Promote new model to Production
            client.transition_model_version_stage(
                name=MODEL_NAME,
                version=new_version.version,
                stage="Production"
            )
            
            logging.info(f"✅ Promoted model v{new_version.version} to Production!")
            logging.info(f"   RMSE improved: {current_rmse:.2f} → {new_rmse:.2f}")
        else:
            logging.warning("Could not find new model version to promote")
    else:
        logging.info(f"New model not significantly better. Keeping current Production.")
        logging.info(f"   Current: {current_rmse:.2f}, New: {new_rmse:.2f}")


# =============================================================================
# DAG Definition
# =============================================================================

with DAG(
    dag_id="retrain_pipeline",
    default_args=default_args,
    description="Daily model retraining with automatic promotion",
    schedule_interval="0 2 * * *",  # Daily at 2 AM UTC
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["mlops", "retraining", "production"],
    max_active_runs=1,
) as dag:
    
    # Task 1: Check for new data
    check_data = BranchPythonOperator(
        task_id="check_data_freshness",
        python_callable=check_data_freshness,
        provide_context=True,
    )
    
    # Skip path
    skip_retrain = PythonOperator(
        task_id="skip_retraining",
        python_callable=skip_retraining_task,
        provide_context=True,
    )
    
    # Task 2: Run dbt transformations
    run_dbt = BashOperator(
        task_id="run_dbt_transformations",
        bash_command=f"cd {DBT_PROJECT_DIR} && dbt run --profiles-dir {DBT_PROJECT_DIR}",
    )
    
    # Task 3: Train model
    train_model = PythonOperator(
        task_id="train_model",
        python_callable=run_training,
        provide_context=True,
    )
    
    # Task 4: Evaluate and promote
    evaluate_promote = PythonOperator(
        task_id="evaluate_and_promote",
        python_callable=evaluate_and_promote,
        provide_context=True,
    )
    
    # Task 5: Notify model API to reload
    reload_model_api = BashOperator(
        task_id="reload_model_api",
        bash_command='curl -X POST http://model-api:8000/model/reload || echo "API reload skipped"',
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )
    
    # Define task dependencies
    check_data >> [run_dbt, skip_retrain]
    run_dbt >> train_model >> evaluate_promote >> reload_model_api
