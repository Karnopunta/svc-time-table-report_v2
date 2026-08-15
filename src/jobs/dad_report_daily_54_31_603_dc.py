"""
DAD Report Daily 54 31 603 DC1 - Production Job.

Workflow:
  0. Check process switch (config_process_switch) - skip if OFF
  1. Calculate date range (daily)
  2. Execute opcode_54.sql and keep result for sheet "opcode_54"
  3. Release temporary memory
  4. Execute opcode_31.sql
  5. Execute opcode_603.sql
  6. Inner join opcode_31 and opcode_603 on (awb, sc)
  7. Calculate selisih in hours where oper_time_603 > oper_time_31
  8. Group by tanggal and sc into 30-minute buckets up to 5 hours
  9. Export to Excel with sheets: opcode_54, opcode_31_603
 10. Upload to OneDrive (finance billing)
 11. Send email with share link (no attachment)
 12. Delete report file after upload
 13. Update last_execute_time in config_process_switch
"""
from __future__ import annotations

import gc
import logging
import os
from typing import Dict, Optional

import pandas as pd

from ..db.repository import oauth_repository
from ..interfaces.ETLJobBase import ETLJobBase
from ..utils import config_helpers, dateutils, email_notifier, onedrive_uploader, query_loader

logger = logging.getLogger(__name__)


class DadReportDaily5431603DcJob(ETLJobBase):
    """DAD Report Daily 54 31 603 DC1 job."""

    SCHEDULE_TYPE = "daily"
    OUTPUT_FORMAT = "xlsx"
    FILE_PATH = "./data/reports"
    FILENAME_TEMPLATE = "DAD_Daily_Report_Leadtime_Productivity_DC1_${DATE}"
    TEMP_PATH = "./temp"

    ENABLE_UPLOAD = True
    SCAN_ID = "sharepoint_finance"
    UPLOAD_FOLDER = "Documents/Projects/Report_Daily/DAD_DAILY_REPORT_DC_PRODUCTIVITY"

    EMAIL_ENABLED = True

    SQL_54 = "src/sql/dc_report/opcode_54.sql"
    SQL_31 = "src/sql/dc_report/opcode_31.sql"
    SQL_603 = "src/sql/dc_report/opcode_603.sql"
    SQL_OPCODE = "src/sql/dc_report/opcode.sql"
    SQL_SORTPLAN_603 = "src/sql/dc_report/sortplan_603.sql"
    SQL_OPCODE_30_SC = "src/sql/dc_report/opcode_30_sc_to_dc.sql"
    SQL_OPCODE_45 = "src/sql/dc_report/opcode_45.sql"
    ## newly added for dc report
    SQL_OPCODE_30_DC = "src/sql/dc_report/opcode_30_dc_to_sc.sql"
    SQL_OPCODE_31_DC = "src/sql/dc_report/opcode_31_dc_to_sc.sql"

    LOAD_DATA_OPCODES = [30, 31, 618]
    LOAD_DATA_SORTPLAN_COLS = [
        "PRIMARY 1", "PRIMARY 2", "HVDOC",
        "SCND 1", "SCND 2", "SCND 3", "SCND 4", "SCND 5",
    ]

    BUCKETS = [
        ("0-0,5", 0.0, 0.5),
        ("0,5-1", 0.5, 1.0),
        ("1-1,5", 1.0, 1.5),
        ("1,5-2", 1.5, 2.0),
        ("2-2,5", 2.0, 2.5),
        ("2,5-3", 2.5, 3.0),
        ("3-3,5", 3.0, 3.5),
        ("3,5-4", 3.5, 4.0),
        ("4-4,5", 4.0, 4.5),
        ("4,5-5", 4.5, 5.0),
    ]

    def process(self):
        cfg = self.config
        script_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

        if not oauth_repository.get_process_switch(self.conn, self.job_code):
            self.logger.warning(f"Process switch is OFF for {self.job_code} - skipping")
            return

        reference_date = cfg.get("REPORT", {}).get("REFERENCE_DATE")
        start_date, end_date = dateutils.calculate_date_range(
            self.SCHEDULE_TYPE, reference_date
        )
        self.logger.info(
            f"Schedule: {self.SCHEDULE_TYPE} | Range: {start_date} -> {end_date}"
        )

        params = {"STARTDATE": start_date, "ENDDATE": end_date}

        self.logger.info("Executing load_data sheet (opcodes 30, 31, 618, 603)")
        df_load_data = self._build_load_data_sheet(params, script_dir)
        self.logger.info(f"load_data rows: {len(df_load_data)}")

        gc.collect()

        self.logger.info("Executing opcode_54")
        df_54 = self._run_sql_to_df(os.path.join(script_dir, self.SQL_54), params)
        self.logger.info(f"opcode_54 rows: {len(df_54)}")

        gc.collect()

        self.logger.info("Executing opcode_31")
        df_31 = self._run_sql_to_df(os.path.join(script_dir, self.SQL_31), params)
        self.logger.info(f"opcode_31 rows: {len(df_31)}")

        gc.collect()

        self.logger.info("Executing opcode_603 (batched by AWB from opcode_31)")
        df_603 = self._run_sql_603_batched(
            os.path.join(script_dir, self.SQL_603), params, df_31
        )
        self.logger.info(f"opcode_603 rows: {len(df_603)}")

        df_31_603 = self._build_joined_bucket_result(df_31, df_603)
        self.logger.info(f"opcode_31_603 rows: {len(df_31_603)}")

        del df_31
        del df_603
        gc.collect()

        self.logger.info("Executing opcode_30_SC")
        df_opcode_30_SC = self._run_sql_to_df(os.path.join(script_dir, self.SQL_OPCODE_30_SC), params)
        self.logger.info(f"opcode_30_SC rows: {len(df_opcode_30_SC)}")

        self.logger.info("Executing opcode_30_DC")
        df_opcode_30_DC = self._run_sql_to_df(os.path.join(script_dir, self.SQL_OPCODE_30_DC), params)
        self.logger.info(f"opcode_30_DC rows: {len(df_opcode_30_DC)}")

        self.logger.info("Executing opcode_31_DC")
        df_opcode_31_DC = self._run_sql_to_df(os.path.join(script_dir, self.SQL_OPCODE_31_DC), params)
        self.logger.info(f"opcode_31_DC rows: {len(df_opcode_31_DC)}")

        self.logger.info("Executing opcode_45")
        df_opcode_45 = self._run_sql_to_df(os.path.join(script_dir, self.SQL_OPCODE_45), params)
        self.logger.info(f"opcode_45 rows: {len(df_opcode_45)}")

        gc.collect()

        date_stamp = dateutils.date_for_filename(start_date)
        filename = config_helpers.resolve_path(
            self.FILENAME_TEMPLATE,
            {
                "SCHEDULE_TYPE": self.SCHEDULE_TYPE,
                "DATE": date_stamp,
                "STARTDATE": date_stamp,
                "ENDDATE": date_stamp,
            },
        )
        output_file = os.path.join(self.FILE_PATH, f"{filename}.xlsx")
        output_file = config_helpers.resolve_path(output_file, cfg)
        self.logger.info(f"Output: {output_file}")

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with pd.ExcelWriter(output_file, engine="openpyxl") as writer:
            df_54.to_excel(writer, sheet_name="opcode_54", index=False)
            df_31_603.to_excel(writer, sheet_name="leadtime_31_603", index=False)
            df_load_data.to_excel(writer, sheet_name="load_data", index=False)
            df_opcode_30_SC.to_excel(writer, sheet_name="opcode_30_SC_to_DC", index=False)
            df_opcode_30_DC.to_excel(writer, sheet_name="opcode_30_DC_to_SC", index=False)
            df_opcode_31_DC.to_excel(writer, sheet_name="opcode_31_DC_to_SC", index=False)
            df_opcode_45.to_excel(writer, sheet_name="opcode_45", index=False)

        self.logger.info(f"Report exported -> {output_file}")

        file_link = ""
        if self.ENABLE_UPLOAD:
            file_link = self._upload_to_sharepoint(cfg, output_file)
        else:
            self.logger.info("Upload disabled - skipping")

        if self.EMAIL_ENABLED:
            self._send_notification(
                cfg,
                script_dir,
                start_date,
                end_date,
                output_file,
                file_link,
            )

        try:
            if os.path.exists(output_file):
                os.remove(output_file)
                self.logger.info(f"File deleted: {output_file}")
        except OSError as del_err:
            self.logger.warning(f"Failed to delete file {output_file}: {del_err}")

        try:
            oauth_repository.update_last_execute_time(
                self.conn,
                self.job_code,
                filenames=[
                    {"filename": os.path.basename(output_file), "type": self.OUTPUT_FORMAT}
                ],
            )
            self.logger.info(f"last_execute_time updated for {self.job_code}")
        except Exception as e:
            self.logger.warning(f"Failed to update last_execute_time: {e}")

        self.logger.info("DAD Report Daily 54 31 603 DC1 job completed successfully")

    def _build_load_data_sheet(
        self,
        params: Dict[str, str],
        script_dir: str,
    ) -> pd.DataFrame:
        """Run opcodes 30/31/618 via opcode.sql and 603 via sortplan_603.sql, then denormalize."""
        opcode_sql_path = os.path.join(script_dir, self.SQL_OPCODE)
        sortplan_sql_path = os.path.join(script_dir, self.SQL_SORTPLAN_603)

        KEY_COLS = ["tanggal", "nik", "nama", "jabatan", "hour"]

        # --- Step 1: run opcode.sql for each of 30, 31, 618 sequentially ---
        opcode_frames = []
        for opcode in self.LOAD_DATA_OPCODES:
            opcode_params = dict(params)
            opcode_params["OPCODE"] = str(opcode)
            df = self._run_sql_to_df(opcode_sql_path, opcode_params)
            self.logger.info(f"load_data opcode_{opcode} rows: {len(df)}")
            opcode_frames.append(df)
            gc.collect()

        # --- Step 2: pivot 30/31/618 into wide format (one column per opcode) ---
        if opcode_frames:
            df_all_opcodes = pd.concat(opcode_frames, ignore_index=True)
        else:
            df_all_opcodes = pd.DataFrame(columns=KEY_COLS + ["opcode", "total"])

        if not df_all_opcodes.empty:
            df_pivot = (
                df_all_opcodes
                .pivot_table(
                    index=KEY_COLS,
                    columns="opcode",
                    values="total",
                    aggfunc="sum",
                    fill_value=0,
                )
                .reset_index()
            )
            df_pivot.columns.name = None
            # Rename integer opcode keys to string column names (30 -> "30", etc.)
            df_pivot = df_pivot.rename(
                columns={op: str(op) for op in self.LOAD_DATA_OPCODES if op in df_pivot.columns}
            )
        else:
            df_pivot = pd.DataFrame(columns=KEY_COLS + [str(op) for op in self.LOAD_DATA_OPCODES])

        # Ensure all opcode columns are present
        for op in self.LOAD_DATA_OPCODES:
            col = str(op)
            if col not in df_pivot.columns:
                df_pivot[col] = 0

        # --- Step 3: run sortplan_603.sql for opcode 603 ---
        df_603_sp = self._run_sql_to_df(sortplan_sql_path, params)
        self.logger.info(f"load_data sortplan_603 rows: {len(df_603_sp)}")

        # Ensure all sortplan columns are present (with 0 if missing)
        for col in self.LOAD_DATA_SORTPLAN_COLS:
            if col not in df_603_sp.columns:
                df_603_sp[col] = 0

        # --- Step 4: outer-merge pivot with sortplan on KEY_COLS ---
        sortplan_merge_cols = KEY_COLS + self.LOAD_DATA_SORTPLAN_COLS
        if df_603_sp.empty:
            df_merged = df_pivot.copy()
            for col in self.LOAD_DATA_SORTPLAN_COLS:
                df_merged[col] = 0
        else:
            df_merged = pd.merge(
                df_pivot,
                df_603_sp[sortplan_merge_cols],
                on=KEY_COLS,
                how="outer",
            )

        # --- Step 5: fill NaN and cast numeric columns to int ---
        numeric_cols = [str(op) for op in self.LOAD_DATA_OPCODES] + self.LOAD_DATA_SORTPLAN_COLS
        for col in numeric_cols:
            if col not in df_merged.columns:
                df_merged[col] = 0
            df_merged[col] = df_merged[col].fillna(0).astype(int)

        # --- Step 6: rename key columns to desired output headers ---
        df_merged = df_merged.rename(
            columns={
                "nik": "NIK",
                "nama": "NAMA",
                "jabatan": "JABATAN",
                "hour": "TIME",
            }
        )

        final_cols = (
            ["tanggal", "NIK", "NAMA", "JABATAN", "TIME"]
            + [str(op) for op in self.LOAD_DATA_OPCODES]
            + self.LOAD_DATA_SORTPLAN_COLS
        )
        return (
            df_merged[final_cols]
            .sort_values(["tanggal", "NIK", "TIME"])
            .reset_index(drop=True)
        )

    def _run_sql_to_df(self, sql_path: str, params: Dict[str, str]) -> pd.DataFrame:
        with open(sql_path, "r", encoding="utf-8") as f:
            raw_sql = f.read()
        rendered_sql = query_loader.inject_parameters(raw_sql, params)
        return pd.read_sql_query(rendered_sql, self.conn)

    def _run_sql_603_batched(
        self,
        sql_path: str,
        params: Dict[str, str],
        df_31: pd.DataFrame,
        batch_size: int = 3000,
    ) -> pd.DataFrame:
        awb_list = df_31["awb"].dropna().unique().tolist()
        self.logger.info(
            f"opcode_603 batching: {len(awb_list)} unique AWBs, "
            f"batch_size={batch_size}"
        )

        with open(sql_path, "r", encoding="utf-8") as f:
            raw_sql = f.read()

        frames = []
        for i in range(0, len(awb_list), batch_size):
            batch = awb_list[i : i + batch_size]
            awb_in_clause = ",".join(
                "'" + str(awb).replace("'", "''") + "'" for awb in batch
            )
            batch_params = dict(params)
            batch_params["AWB_LIST"] = awb_in_clause
            rendered_sql = query_loader.inject_parameters(raw_sql, batch_params)
            df_batch = pd.read_sql_query(rendered_sql, self.conn)
            frames.append(df_batch)
            self.logger.info(
                f"  batch {i // batch_size + 1}: "
                f"{len(batch)} AWBs -> {len(df_batch)} rows"
            )

        if frames:
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame(columns=["awb", "sc_destination", "oper_time"])

    def _build_joined_bucket_result(
        self,
        df_31: pd.DataFrame,
        df_603: pd.DataFrame,
    ) -> pd.DataFrame:
        joined = pd.merge(
            df_31,
            df_603,
            on=["awb", "sc_destination"],
            how="inner",
            suffixes=("_31", "_603"),
        )

        if joined.empty:
            return pd.DataFrame(columns=["tanggal", "sc"] + [b[0] for b in self.BUCKETS])

        joined["oper_time_31"] = pd.to_datetime(joined["oper_time_31"], errors="coerce")
        joined["oper_time_603"] = pd.to_datetime(joined["oper_time_603"], errors="coerce")

        joined = joined[
            joined["oper_time_31"].notna()
            & joined["oper_time_603"].notna()
            & (joined["oper_time_603"] > joined["oper_time_31"])
        ].copy()

        if joined.empty:
            return pd.DataFrame(columns=["tanggal", "sc"] + [b[0] for b in self.BUCKETS])

        joined["selisih_jam"] = (
            joined["oper_time_603"] - joined["oper_time_31"]
        ).dt.total_seconds() / 3600.0
        joined = joined[(joined["selisih_jam"] > 0.0) & (joined["selisih_jam"] <= 5.0)].copy()

        if joined.empty:
            return pd.DataFrame(columns=["tanggal", "sc"] + [b[0] for b in self.BUCKETS])

        joined["tanggal"] = joined["oper_time_603"].dt.date

        result = joined[["tanggal", "sc_destination"]].drop_duplicates().copy()

        for col_name, lower, upper in self.BUCKETS:
            bucket_counts = (
                joined[(joined["selisih_jam"] > lower) & (joined["selisih_jam"] <= upper)]
                .groupby(["tanggal", "sc_destination"])
                .size()
                .reset_index(name=col_name)
            )
            result = result.merge(bucket_counts, on=["tanggal", "sc_destination"], how="left")

        for col_name, _, _ in self.BUCKETS:
            result[col_name] = result[col_name].fillna(0).astype(int)

        final_cols = ["tanggal", "sc_destination"] + [b[0] for b in self.BUCKETS]
        result = result[final_cols].sort_values(["tanggal", "sc_destination"]).reset_index(drop=True)
        return result

    def _resolve_scan_config(self, cfg: Dict) -> Optional[Dict]:
        scans = cfg.get("SHAREPOINT_CONTENT_EXTRACTOR", {}).get("SCANS", [])
        scan_config = next((s for s in scans if s.get("SCAN_ID") == self.SCAN_ID), None)
        if not scan_config:
            self.logger.error(
                f"SCAN_ID '{self.SCAN_ID}' not found in "
                "SHAREPOINT_CONTENT_EXTRACTOR.SCANS - upload skipped"
            )
            return None

        import re

        pattern = r"\$\{(\w+)\}"
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
                    item_id=item_id,
                    conn=self.conn,
                    config=upload_cfg,
                )
            except Exception:
                self.logger.warning("Could not create share link; using webUrl")

        self.logger.info(f"Upload done - link: {file_link}")
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
        smtp_cfg = oauth_repository.get_smtp_config(self.conn, self.job_code)

        if not smtp_cfg or not smtp_cfg.get("email"):
            self.logger.warning("No SMTP config found - skipping notification")
            return

        to_email = smtp_cfg["email"]
        cc_email = smtp_cfg.get("cc_email")
        bcc_email = smtp_cfg.get("bcc_email")

        template_path_rel = cfg.get("EMAIL", {}).get(
            "TEMPLATE_PATH", "config/config/email_template.jinja2"
        )
        template_path = os.path.join(script_dir, template_path_rel)

        subject = (
            f"DAD Report Daily 54 31 603 DC "
            f"({dateutils.format_date(end_date, '%d-%m-%Y')})"
        )

        period_start = dateutils.format_date(end_date, "%d %B %Y") + " 00:00"
        period_end = dateutils.format_date(end_date, "%d %B %Y") + " 15:00"

        context = {
            "report_title": "DAD Report Daily 54 31 603 DC",
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
        self.logger.info(f"Email sent to {to_email} with link")
