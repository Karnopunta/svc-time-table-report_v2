"""Base class for ETL jobs."""
from abc import ABC, abstractmethod
import uuid

import psycopg2

from ..utils.timeutils import now_tz

class ETLJobBase(ABC):
    def __enter__(self):
        """
        Enter the runtime context related to this object.

        Use this method to set up resources that should be acquired at the start of a with block
        (such as opening files or other resources that need explicit cleanup).
        For most ETL jobs, open the database connection in __init__ so it is available throughout the job lifecycle.

        Returns:
            self: The job instance, ready for use in a with statement.
        """
        self.logger.info("Entering ETL job context.")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.info("Exiting ETL job context.")
        if exc_type:
            self.finish(status="failed", error_msg=str(exc_val))
        else:
            self.finish(status="success", error_msg=None)
        if hasattr(self, "conn") and self.conn and not self.conn.closed:
            self.conn.close()
            self.logger.info("Database connection closed.")
        return False

    def __init__(self, job_code, repo, config, logger):
        self.job_code = job_code
        self.repo = repo
        self.config = config
        self.logger = logger
        self.conn = self._create_db_connection()
        self.start_time = now_tz()  # Record start time at initialization
        self.job_row = repo.get_job_row_by_code(self.conn, job_code)
        if not self.job_row:
            raise ValueError(f"job_code '{job_code}' not found in logging.etl_job")
        if not self.job_row["enabled"]:
            raise ValueError(f"job_code '{job_code}' is disabled in logging.etl_job")
        self.job_id = self.job_row["job_id"]
        self.interval_type = self.job_row["interval_type"]
        self.interval_value = float(self.job_row["interval_value"])
        self.interval_multiplier = float(self.job_row["interval_multiplier"])
        self.max_attempt = int(self.job_row["max_attempt"])

        self.run_id = repo.start_run(
            self.conn,
            self.job_id,
            run_code=str(uuid.uuid4()),
        )
        self.logger.info(f"Started run_id: {self.run_id} for job_code: {job_code}")
        self.logger.info(f"Job execution started at: {self.start_time}")

    def _create_db_connection(self):
        """
        Create and return a new database connection using the job config.

        Returns:
            psycopg2 connection object
        """
        return psycopg2.connect(
            host=self.config.get("DB_HOST", "127.0.0.1"),
            port=self.config.get("DB_PORT", 5432),
            dbname=self.config.get("DB_NAME", "your_db"),
            user=self.config.get("DB_USER", "your_user"),
            password=self.config.get("DB_PASSWORD", "your_password"),
        )

    @abstractmethod
    def process(self):
        pass

    @staticmethod
    def generate_uuid():
        """
        Generate a new UUID string for use as a unique identifier (e.g., request_batch_id).

        Returns:
            str: A new UUID string.
        """
        return str(uuid.uuid4())

    def finish(self, status="success", error_msg=None):
        self.finish_time = now_tz()  # Record finish time
        self.logger.info(f"Job execution finished at: {self.finish_time}")
        duration = self.finish_time - self.start_time
        self.logger.info(f"Total execution time: {duration}")
        duration_ms = int(duration.total_seconds() * 1000)
        self.repo.finish_run(
            self.conn,
            self.run_id,
            status=status,
            error_code=None,
            error_msg=error_msg,
            duration_ms=duration_ms,
        )
        if status == "success":
            self.logger.info("Application finished successfully!")
