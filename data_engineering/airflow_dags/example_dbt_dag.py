"""
Example Airflow DAG - dbt Transformation Pipeline
=================================================
This DAG runs dbt transformations on a schedule.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    'owner': 'data-engineering',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='dbt_transformation_pipeline',
    default_args=default_args,
    description='Run dbt models to transform raw data into features',
    schedule_interval='@hourly',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['dbt', 'transformation', 'hourly'],
) as dag:
    
    dbt_deps = BashOperator(
        task_id='dbt_deps',
        bash_command='cd /opt/airflow/dbt && dbt deps',
    )
    
    dbt_run_staging = BashOperator(
        task_id='dbt_run_staging',
        bash_command='cd /opt/airflow/dbt && dbt run --select staging.*',
    )
    
    dbt_run_intermediate = BashOperator(
        task_id='dbt_run_intermediate',
        bash_command='cd /opt/airflow/dbt && dbt run --select intermediate.*',
    )
    
    dbt_run_marts = BashOperator(
        task_id='dbt_run_marts',
        bash_command='cd /opt/airflow/dbt && dbt run --select marts.*',
    )
    
    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='cd /opt/airflow/dbt && dbt test',
    )
    
    # Task dependencies
    dbt_deps >> dbt_run_staging >> dbt_run_intermediate >> dbt_run_marts >> dbt_test
