"""Database repository helpers for ETL metadata and delivery tables."""

import logging


logger = logging.getLogger(__name__)


def upsert_states_bulk(conn, states):
    """
    Bulk upsert multiple delivery state records into logging.etl_delivery_state.

    Args:
        conn: Database connection.
        states: List of dicts, each containing the same keys as upsert_state's
            arguments (except conn).

    Returns:
        None
    """
    if not states:
        return
    try:
        with conn.cursor() as cur:
            args_list = [
                (
                    s["idempotency_key"],
                    s["job_id"],
                    s["order_id"],
                    s["status"],
                    s["attempt_no"],
                    s["next_retry_at"],
                    s["last_run_id"],
                    s["last_error_code"],
                    s["last_error_msg"],
                    s["max_attempt"],
                    s["interval_type"],
                    s["interval_value"],
                    s["interval_multiplier"],
                )
                for s in states
            ]
            cur.executemany(
                """
                INSERT INTO logging.etl_delivery_state
                    (idempotency_key, job_id, order_id, status, last_attempt_no,
                     next_retry_at, last_run_id, last_error_code, last_error_msg,
                     last_updated_at, max_attempt, interval_type, interval_value, interval_multiplier)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), %s,%s,%s,%s)
                ON CONFLICT (idempotency_key) DO UPDATE
                   SET status = EXCLUDED.status,
                       last_attempt_no = EXCLUDED.last_attempt_no,
                       next_retry_at = EXCLUDED.next_retry_at,
                       last_run_id = EXCLUDED.last_run_id,
                       last_error_code = EXCLUDED.last_error_code,
                       last_error_msg = EXCLUDED.last_error_msg,
                       last_updated_at = now(),
                       max_attempt = EXCLUDED.max_attempt,
                       interval_type = EXCLUDED.interval_type,
                       interval_value = EXCLUDED.interval_value,
                       interval_multiplier = EXCLUDED.interval_multiplier
                """,
                args_list,
            )
            conn.commit()
    except Exception:
        logger.exception("Error in upsert_states_bulk")
        raise


def insert_attempts_bulk(conn, attempts):
    """
    Bulk insert multiple attempt records into logging.etl_delivery_attempt.

    Args:
        conn: Database connection.
        attempts: List of dicts, each containing the same keys as record_attempt's
            arguments (except conn).

    Example of attempts:
        [
            {
                'attempt_key': ..., 'run_id': ..., 'job_id': ..., 'request_batch_id': ...,
                'idempotency_key': ..., 'attempt_no': ..., 'http_status': ...,
                'outcome': ..., 'error_class': ..., 'error_code': ..., 'error_message': ...
            },
            ...
        ]

    Returns:
        None
    """
    if not attempts:
        return
    try:
        with conn.cursor() as cur:
            args_list = [
                (
                    a["attempt_key"],
                    a["run_id"],
                    a["job_id"],
                    a["request_batch_id"],
                    a["idempotency_key"],
                    a["attempt_no"],
                    a["http_status"],
                    a["outcome"],
                    a["error_class"],
                    a["error_code"],
                    a["error_message"],
                )
                for a in attempts
            ]
            cur.executemany(
                """
                INSERT INTO logging.etl_delivery_attempt (
                    attempt_key, run_id, job_id, request_batch_id, idempotency_key,
                    attempt_no, http_status, outcome, error_class, error_code, error_message
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                args_list,
            )
            conn.commit()
    except Exception:
        logger.exception("Error in insert_attempts_bulk")
        raise


def start_run(conn, job_id: int, run_code: str | None = None) -> int:
    """
    Start a new ETL run for a given job.

    Args:
        job_id (int): The ID of the ETL job.
        run_code (str, optional): An optional run code for the run.

    Returns:
        int: The run_id of the newly created ETL run.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO logging.etl_run(job_id, run_code, started_at, status)
                VALUES (%s, %s, now(), 'running')
                RETURNING run_id
                """,
                (job_id, run_code),
            )
            conn.commit()
            return cur.fetchone()[0]
    except Exception:
        logger.exception("Error in start_run")
        raise


def finish_run(
    conn,
    run_id: int,
    status: str,
    error_code: str | None,
    error_msg: str | None,
    duration_ms: int | None,
):
    """
    Mark an ETL run as finished and update its status and error info.

    Args:
        run_id (int): The run ID to finish.
        status (str): The final status (e.g., 'success', 'failed').
        error_code (str, optional): Error code if failed.
        error_msg (str, optional): Error message if failed.
        duration_ms (int, optional): Total runtime in milliseconds.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE logging.etl_run
                   SET finished_at = now(),
                       duration_ms = %s,
                       status = %s,
                       error_code = %s,
                       error_msg = %s
                 WHERE run_id = %s
                """,
                (duration_ms, status, error_code, error_msg, run_id),
            )
            conn.commit()
    except Exception:
        logger.exception("Error in finish_run")
        raise


def upsert_state(
    conn,
    idempotency_key: str,
    job_id: int,
    order_id: str,
    status: str,
    attempt_no: int,
    next_retry_at,
    last_run_id: int | None,
    last_error_code: str | None,
    last_error_msg: str | None,
    max_attempt: int,
    interval_type: str,
    interval_value: int,
    interval_multiplier: float,
):
    """
    Insert or update the ETL delivery state for a specific job and order.

    Table PK:
        idempotency_key (TEXT PRIMARY KEY): Unique key for the delivery attempt.
        Each item in each ETL job should have a different idempotency_key value,
        because the same item can be processed in many ETL jobs.

    Args:
        idempotency_key (str): Unique key for the delivery attempt and the primary key of the table.
            Should be unique per item per ETL job.
        job_id (int): The ID of the ETL job.
        order_id (str): The order identifier.
        status (str): Current status of the delivery (e.g., 'pending', 'delivered').
        attempt_no (int): The current attempt number.
        next_retry_at: Timestamp for the next retry attempt.
        last_run_id (int, optional): The last run ID associated with this delivery.
        last_error_code (str, optional): The last error code encountered.
        last_error_msg (str, optional): The last error message encountered.
        max_attempt (int): Maximum number of delivery attempts allowed.
        interval_type (str): Type of retry interval (e.g., 'fixed', 'exponential').
        interval_value (int): Value for the retry interval.
        interval_multiplier (float): Multiplier for the retry interval.

    Returns:
        None
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO logging.etl_delivery_state
                    (idempotency_key, job_id, order_id, status, last_attempt_no,
                     next_retry_at, last_run_id, last_error_code, last_error_msg,
                     last_updated_at, max_attempt, interval_type, interval_value, interval_multiplier)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now(), %s,%s,%s,%s)
                ON CONFLICT (idempotency_key) DO UPDATE
                   SET status = EXCLUDED.status,
                       last_attempt_no = EXCLUDED.last_attempt_no,
                       next_retry_at = EXCLUDED.next_retry_at,
                       last_run_id = EXCLUDED.last_run_id,
                       last_error_code = EXCLUDED.last_error_code,
                       last_error_msg = EXCLUDED.last_error_msg,
                       last_updated_at = now(),
                       max_attempt = EXCLUDED.max_attempt,
                       interval_type = EXCLUDED.interval_type,
                       interval_value = EXCLUDED.interval_value,
                       interval_multiplier = EXCLUDED.interval_multiplier
                """,
                (
                    idempotency_key,
                    job_id,
                    order_id,
                    status,
                    attempt_no,
                    next_retry_at,
                    last_run_id,
                    last_error_code,
                    last_error_msg,
                    max_attempt,
                    interval_type,
                    interval_value,
                    interval_multiplier,
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("Error in upsert_state")
        raise


def record_attempt(
    conn,
    attempt_key: str,
    run_id: int,
    job_id: int,
    request_batch_id: str,
    idempotency_key: str,
    attempt_no: int,
    http_status: int | None,
    outcome: str,
    error_class: str | None,
    error_code: str | None,
    error_message: str | None,
):
    """
    Record an attempt to deliver an ETL payload for a specific job and order.

    Args:
        attempt_key (str): Unique key for this delivery attempt.
        run_id (int): The ETL run ID associated with this attempt.
        job_id (int): The ID of the ETL job.
        request_batch_id (str): Identifier for the request batch.
        idempotency_key (str): Unique key for the delivery state.
        attempt_no (int): The attempt number for this delivery.
        http_status (int, optional): HTTP status code returned by the delivery attempt.
        outcome (str): Outcome of the attempt (e.g., 'success', 'failed').
        error_class (str, optional): Class/type of error encountered, if any.
        error_code (str, optional): Error code, if any.
        error_message (str, optional): Error message, if any.

    Returns:
        None
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO logging.etl_delivery_attempt (
                    attempt_key, run_id, job_id, request_batch_id, idempotency_key,
                    attempt_no, http_status, outcome, error_class, error_code, error_message
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    attempt_key,
                    run_id,
                    job_id,
                    request_batch_id,
                    idempotency_key,
                    attempt_no,
                    http_status,
                    outcome,
                    error_class,
                    error_code,
                    error_message,
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("Error in record_attempt")
        raise


def park_to_dead_letter(
    conn,
    idempotency_key: str,
    job_id: int,
    order_id: str,
    reason_code: str,
    reason_msg: str,
    last_error_code: str | None,
    last_error_msg: str | None,
    last_attempt_no: int,
    last_run_id: int | None,
):
    """
    Move a failed ETL delivery to the dead letter table for further inspection
    or manual intervention.

    Args:
        idempotency_key (str): Unique key for the delivery attempt.
        job_id (int): The ID of the ETL job.
        order_id (str): The order identifier.
        reason_code (str): Code representing the reason for dead lettering.
        reason_msg (str): Message describing the reason for dead lettering.
        last_error_code (str, optional): The last error code encountered.
        last_error_msg (str, optional): The last error message encountered.
        last_attempt_no (int): The last attempt number for this delivery.
        last_run_id (int, optional): The last run ID associated with this delivery.

    Returns:
        None
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO logging.etl_dead_letter (
                    idempotency_key, job_id, order_id, reason_code, reason_msg,
                    last_error_code, last_error_msg, last_attempt_no, last_run_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (idempotency_key) DO NOTHING
                """,
                (
                    idempotency_key,
                    job_id,
                    order_id,
                    reason_code,
                    reason_msg,
                    last_error_code,
                    last_error_msg,
                    last_attempt_no,
                    last_run_id,
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("Error in park_to_dead_letter")
        raise


def get_job_row_by_code(conn, job_code: str):
    """
    Retrieve a job's configuration and metadata from the database by its job code.

    Args:
        job_code (str): The unique code identifying the ETL job.

    Returns:
        dict or None: A dictionary containing job configuration fields if found,
        otherwise None.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT job_id, job_code, job_name, schedule_times, schedule_tz,
                       sla_minutes, grace_minutes, max_attempt,
                       interval_type, interval_value, interval_multiplier, enabled
                  FROM logging.etl_job
                 WHERE job_code = %s
                """,
                (job_code,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))
    except Exception:
        logger.exception("Error in get_job_row_by_code")
        raise


def insert_request_batch(
    conn,
    request_batch_id: str,
    run_id: int,
    job_id: int,
    attempt_group: int,
    request_json,
    response_json=None,
    http_status=None,
):
    """
    Insert a new request batch record into logging.etl_request_batch.

    Args:
        request_batch_id (str): UUID for the request batch (primary key).
        run_id (int): The ETL run ID.
        job_id (int): The ETL job ID.
        attempt_group (int): Logical wave/group in the same run.
        request_json: The full request body (JSON-serializable).
        response_json: The raw response body (JSON-serializable, optional).
        http_status (int, optional): HTTP status code of the API call.

    Returns:
        None
    """
    import json

    try:
        req_json_str = json.dumps(request_json) if request_json is not None else None
        resp_json_str = json.dumps(response_json) if response_json is not None else None
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO logging.etl_request_batch (
                    request_batch_id, run_id, job_id, attempt_group,
                    request_json, response_json, http_status
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    request_batch_id,
                    run_id,
                    job_id,
                    attempt_group,
                    req_json_str,
                    resp_json_str,
                    http_status,
                ),
            )
            conn.commit()
    except Exception:
        logger.exception("Error in insert_request_batch")
        raise
