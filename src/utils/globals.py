"""Shared constants for the ETL boilerplate."""
import pytz

jakarta_tz = pytz.timezone("Asia/Jakarta")

# src/utils/globals.py
API_TIMEOUT = 60
API_VERSION = "7.1"
REL_BATCH_SIZE = 200
DETAIL_BATCH_SIZE = 200
INSERT_BATCH_SIZE = 1000
