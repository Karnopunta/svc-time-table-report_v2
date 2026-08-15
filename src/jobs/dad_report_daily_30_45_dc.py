"""
DAD Report Daily 30 45 DC – Production Job.

Daily report combining opcode_30 and opcode_45 data.
Workflow:
  0. Check process switch (config_process_switch) – skip if OFF
  1. Calculate date range (daily)
  2. Load SQL queries from manifest (opcode_30, opcode_45)
  3. Build parameterised queries
  4. Export to Excel (.xlsx) – each opcode in its own sheet
  5. Upload to SharePoint (finance billing)
  6. Send email with share link (no attachment)
  7. Delete report file after upload
  8. Update last_execute_time in config_process_switch
"""
from __future__ import annotations

import logging
import os
from typing import Dict, Optional

from ..interfaces.ETLJobBase import ETLJobBase
from ..utils import (
    config_helpers,
    dateutils,
    email_notifier,
    excel_exporter,
    onedrive_uploader,
    query_loader,
)
from ..db.repository import oauth_repository

logger = logging.getLogger(__name__)


class DadReportDaily3045DcJob(ETLJobBase):
    """
    DAD Report Daily 30 45 DC job.

    Runs opcode_30.sql and opcode_45.sql, exports results to a single
    Excel file with separate sheets per opcode, uploads to OneDrive
    (finance billing), and sends the share link via email.
    """

    # ────── JOB DEFAULTS ─────────────────────────────────────────────
    SCHEDULE_TYPE = "daily"
    OUTPUT_FORMAT = "xlsx"
    FILE_PATH = "./data/reports"
    FILENAME_TEMPLATE = "dad_report_daily_30_45_dc_${DATE}"
    TEMP_PATH = "./temp"

    ENABLE_UPLOAD = True
    SCAN_ID = "sharepoint_finance"
    UPLOAD_FOLDER = "Documents/Projects/Report_Daily/DAD_DAILY_REPORT_DC_PRODUCTIVITY"

    EMAIL_ENABLED = True
    MANIFEST_PATH = "src/sql/dc_report/report_dc.json"
    # ─────────────────────────────────────────────────────────────────

    def process(self):
        cfg = self.config
        script_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        # ── 0. Check process switch ──────────────────────────────────
        if not oauth_repository.get_process_switch(self.conn, self.job_code):
            self.logger.warning(
                f"Process switch is OFF for {self.job_code} – skipping"
            )
            return

        # ── 1. Resolve schedule & dates ──────────────────────────────
        reference_date = cfg.get("REPORT", {}).get("REFERENCE_DATE")
        start_date, end_date = dateutils.calculate_date_range(
            self.SCHEDULE_TYPE, reference_date
        )
        self.logger.info(
            f"Schedule: {self.SCHEDULE_TYPE} | Range: {start_date} -> {end_date}"
        )

        # ── 2. Load queries from manifest ────────────────────────────
        manifest_full = os.path.join(script_dir, self.MANIFEST_PATH)
        query_loader.validate_manifest(manifest_full)
        all_queries = query_loader.load_all_queries(manifest_full)
        self.logger.info(f"Loaded {len(all_queries)} query/queries from manifest")

        # ── 3. Load template metadata ────────────────────────────────
        manifest_meta = query_loader.load_manifest_meta(manifest_full)
        template_file = manifest_meta.get("template_file")
        template_header_rows = manifest_meta.get("template_header_rows", 1)

        # ── 4. Build parameterised queries ───────────────────────────
        sheets_config = []
        # STARTDATE = today 00:00, ENDDATE = today 15:30 (data window for DC)
        params = {
            "STARTDATE": f"{end_date} 00:00:00",
            "ENDDATE":   f"{end_date} 15:30:00",
        }

        for q in all_queries:
            rendered_sql = query_loader.inject_parameters(q["sql"], params)
            sheets_config.append((q["sheet_name"], rendered_sql))
            self.logger.info(
                f"Query '{q['name']}' -> sheet '{q['sheet_name']}' "
                f"(date range: {start_date} -> {end_date})"
            )

        # ── 5. Resolve output path ───────────────────────────────────
        date_stamp = dateutils.date_for_filename(end_date)
        filename = config_helpers.resolve_path(
            self.FILENAME_TEMPLATE,
            {
                "SCHEDULE_TYPE": self.SCHEDULE_TYPE,
                "DATE": date_stamp,
                "STARTDATE": date_stamp,
                "ENDDATE": date_stamp,
            },
        )
        ext = "xlsx" if self.OUTPUT_FORMAT == "xlsx" else "csv"
        output_file = os.path.join(self.FILE_PATH, f"{filename}.{ext}")
        output_file = config_helpers.resolve_path(output_file, cfg)
        self.logger.info(f"Output: {output_file} (format={self.OUTPUT_FORMAT})")

        # ── 6. Export report ─────────────────────────────────────────
        result_path = excel_exporter.export_report(
            output_path=output_file,
            sheets_config=sheets_config,
            conn=self.conn,
            output_format=self.OUTPUT_FORMAT,
            append=False,
            format_config={"header_bold": True, "auto_width": True},
            template_file=template_file,
            template_header_rows=template_header_rows,
        )
        self.logger.info(f"Report exported -> {result_path}")

        # ── 7. Upload to SharePoint (conditional) ────────────────────
        file_link = ""

        if self.ENABLE_UPLOAD:
            file_link = self._upload_to_sharepoint(cfg, result_path)
        else:
            self.logger.info("Upload disabled – skipping")

        # ── 8. Send email notification ───────────────────────────────
        if self.EMAIL_ENABLED:
            self._send_notification(
                cfg, script_dir, start_date, end_date,
                output_file, file_link,
            )

        # ── 9. Delete report file after upload/email ─────────────────
        try:
            if os.path.exists(result_path):
                os.remove(result_path)
                self.logger.info(f"File deleted: {result_path}")
        except OSError as del_err:
            self.logger.warning(f"Failed to delete file {result_path}: {del_err}")

        # ── 10. Update last_execute_time ─────────────────────────────
        try:
            oauth_repository.update_last_execute_time(
                self.conn, self.job_code,
                filenames=[{"filename": os.path.basename(result_path), "type": self.OUTPUT_FORMAT}],
            )
            self.logger.info(f"last_execute_time updated for {self.job_code}")
        except Exception as e:
            self.logger.warning(f"Failed to update last_execute_time: {e}")

        self.logger.info("DAD Report Daily 30 45 DC job completed successfully")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_scan_config(self, cfg: Dict) -> Optional[Dict]:
        scans = cfg.get("SHAREPOINT_CONTENT_EXTRACTOR", {}).get("SCANS", [])
        scan_config = next(
            (s for s in scans if s.get("SCAN_ID") == self.SCAN_ID), None
        )
        if not scan_config:
            self.logger.error(
                f"SCAN_ID '{self.SCAN_ID}' not found in "
                f"SHAREPOINT_CONTENT_EXTRACTOR.SCANS – upload skipped"
            )
            return None
        import re
        pattern = r'\$\{(\w+)\}'

        for key, value in scan_config.items():
            if isinstance(value, str):
                def replacer(match):
                    var_name = match.group(1)
                    env_val = os.getenv(var_name)
                    if env_val is None:
                        self.logger.warning(f"Env var ${{{var_name}}} not set")
                        return match.group(0)
                    return env_val

                scan_config[key] = re.sub(pattern, replacer, value)

        return scan_config

    def _upload_to_sharepoint(self, cfg: Dict, result_path: str) -> str:
        scan_config = self._resolve_scan_config(cfg)
        if not scan_config:
            return ""

        self.logger.info(
            f"Using SCAN_ID '{self.SCAN_ID}' -> "
            f"{scan_config.get('ACCOUNT_NAME', 'unknown')}"
        )

        upload_cfg = dict(cfg)
        upload_cfg["ONEDRIVE"] = {
            "UPLOAD_CONFIG_NAME": scan_config.get("UPLOAD_CONFIG_NAME"),
            "TOKEN_CONFIG_NAME": scan_config.get("TOKEN_CONFIG_NAME"),
            "DRIVE_ID": scan_config.get("DRIVE_ID"),
            "UPLOAD_FOLDER": self.UPLOAD_FOLDER,
        }

        upload_result = onedrive_uploader.upload_file(
            file_path=result_path,
            remote_folder=self.UPLOAD_FOLDER,
            conn=self.conn,
            config=upload_cfg,
        )
        file_link = upload_result.get("webUrl", "")

        item_id = upload_result.get("id")
        if item_id:
            try:
                file_link = onedrive_uploader.create_share_link(
                    item_id=item_id, conn=self.conn, config=upload_cfg,
                )
            except Exception:
                self.logger.warning("Could not create share link; using webUrl")

        self.logger.info(f"Upload done – link: {file_link}")
        return file_link

    def _send_notification(
        self,
        cfg: Dict,
        script_dir: str,
        start_date: str,
        end_date: str,
        output_file: str,
        file_link: str,
    ) -> None:
        smtp_cfg = oauth_repository.get_smtp_config(
            self.conn, self.job_code
        )

        if not smtp_cfg or not smtp_cfg.get("email"):
            self.logger.warning("No SMTP config found – skipping notification")
            return

        to_email = smtp_cfg["email"]
        cc_email = smtp_cfg.get("cc_email")
        bcc_email = smtp_cfg.get("bcc_email")

        template_path_rel = cfg.get("EMAIL", {}).get(
            "TEMPLATE_PATH", "config/config/email_template.jinja2"
        )
        template_path = os.path.join(script_dir, template_path_rel)

        subject = (
            f"DAD Report Daily 30 45 DC "
            f"({dateutils.format_date(end_date, '%d-%m-%Y')})"
        )

        period_start = dateutils.format_date(end_date, "%d %B %Y") + " 00:00"
        period_end = dateutils.format_date(end_date, "%d %B %Y") + " 15:00"

        context = {
            "report_title": "DAD Report Daily 30 45 DC",
            "schedule_type": self.SCHEDULE_TYPE,
            "report_date": dateutils.format_date(end_date, "%d %B %Y"),
            "start_date": f"{end_date} 00:00",
            "end_date": f"{end_date} 15:00",
            "period": f"{period_start} - {period_end}",
            "file_name": os.path.basename(output_file),
            "file_link": file_link,
            "generated_at": dateutils.now_jakarta().strftime("%Y-%m-%d %H:%M:%S"),
        }

        email_notifier.send_report_email(
            template_path=template_path,
            to_email=to_email,
            cc_email=cc_email,
            bcc_email=bcc_email,
            subject=subject,
            context=context,
            from_email=${from_email},
            smtp_host=smtp_cfg["host"],
            smtp_port=smtp_cfg.get("port", 587),
            username=smtp_cfg["username"],
            password=smtp_cfg["password"],
        )
        self.logger.info(
            f"Email sent to {to_email} with link"
        )
