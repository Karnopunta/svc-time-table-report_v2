"""Idempotency helpers for ETL jobs."""
import hashlib

def make_key(order_id: str, job_code: str) -> str:
    payload = f"{job_code}:{order_id}".encode()
    return hashlib.sha256(payload).hexdigest()
