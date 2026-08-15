"""Main application entry point."""
import argparse
import logging
import os    

from config.settings import load_config, set_config

from .db import repository as repo
from .utils.helpers import setup_keyring, setup_logging
from .jobs.dad_report_time_table_hub import DADReportTimeTableHubJob
from .jobs.dad_report_daily_30_45_dc import DadReportDaily3045DcJob
from .jobs.dad_report_daily_54_31_603_dc import DadReportDaily5431603DcJob
from .jobs.monitoring_hub_hlm import DadReportDailyMonitoringHubHlmJob
from .jobs.dad_report_daily_dc2 import DadReportDailyDc2Job

# Registry of available job processors
JOB_REGISTRY = {
    "DAD_REPORT_TIME_TABLE_HUB": DADReportTimeTableHubJob,
    "DAD_DAILY_REPORT_DC_DESTINATION": DadReportDaily3045DcJob,
    "DAD_DAILY_REPORT_DC_PRODUCTIVITY": DadReportDaily5431603DcJob,
    "DAD_REPORT_MONITORING_HUB_HLM": DadReportDailyMonitoringHubHlmJob,
    "DAD_DAILY_REPORT_DC2_PRODUCTIVITY": DadReportDailyDc2Job,
}


def main():
    """Main application function."""
    parser = argparse.ArgumentParser(description="Run ETL jobs.")
    parser.add_argument(
        "--job-code",
        default="DAD_REPORT_TIME_TABLE_HUB",
        help="ETL job code to execute.",
    )
    parser.add_argument(
        "--schedule-type",
        default=None,
        help="Override schedule type (daily/weekly/monthly).",
    )
    parser.add_argument(
        "--reference-date",
        default=None,
        help="Override reference date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--output-format",
        default=None,
        help="Override output format (xlsx/csv).",
    )
    args = parser.parse_args()

    logging.getLogger().handlers.clear()
    script_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = load_config(script_dir)
    set_config(config)
    setup_logging(config, script_dir)
    setup_keyring()

    # Apply CLI overrides to config
    if args.schedule_type:
        config.setdefault("REPORT", {})["SCHEDULE_TYPE"] = args.schedule_type
    if args.reference_date:
        config.setdefault("REPORT", {})["REFERENCE_DATE"] = args.reference_date
    if args.output_format:
        config.setdefault("REPORT", {})["OUTPUT_FORMAT"] = args.output_format

    # Route to the correct job class
    job_cls = JOB_REGISTRY.get(args.job_code)
    if not job_cls:
        raise ValueError(
            f"Unknown job code '{args.job_code}'. "
            f"Available: {', '.join(sorted(JOB_REGISTRY.keys()))}"
        )

    with job_cls(args.job_code, repo, config, logging) as processor:
        processor.process()


if __name__ == "__main__":
    main()