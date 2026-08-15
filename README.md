# svc-time-table-report

## Supported Jobs

| Job Code | Description | Docs |
|----------|-------------|------|
| `DAD_DAILY_REPORT_DC_DESTINATION` | report dc opcode 30 & 45 exceptions | [View](docs/jobs/dad_report_daily_30_45_dc.md) |
| `DAD_REPORT_TIME_TABLE_HUB` | report hub time table exceptions | [View](docs/jobs/dad_report_time_table_hub.md) |
| `DAD_DAILY_REPORT_DC_PRODUCTIVITY` | report productivity dc opcode 30,45,31,618,603,54 exceptions | [View](docs/jobs/dad_report_daily_54_31_603_dc.md) |
| `DAD_REPORT_MONITORING_HUB_HLM` | DAD_REPORT_MONITORING_HUB_HLM opcode 30,45,31,618,603,54 exceptions | [View](docs/jobs/monitoring_hub_hlm.md) |


Single-job ETL repository for `DAD_REPORT_TIME_TABLE_HUB`. The job extracts the HUB time table data, groups AWB counts, exports one Excel workbook, and can optionally upload/send email based on runtime config.

## What This Repo Does

This repository currently implements the `DAD_REPORT_TIME_TABLE_HUB` job:

- Loads SQL from `src/sql/time_table_hub/manifest.json`
- Executes the HUB extract in 3-hour windows
- Groups and counts AWB by the HUB keys
- Exports one workbook to `./data/reports`
- Optionally uploads and sends email when enabled in config

## Repository Layout

```text
svc-time-table-report/
├── config/
│   ├── settings.py
│   └── config/
│       ├── local.yaml
│       ├── arif.yaml
│       ├── dev_andre.yaml
│       └── email_template.jinja2
├── docs/
│   └── jobs/
│       └── dad_report_time_table_hub.md
├── src/
│   ├── main.py
│   ├── jobs/
│   │   └── dad_report_time_table_hub.py
│   ├── sql/
│   │   └── time_table_hub/
│   ├── db/
│   └── utils/
├── data/
├── logs/
├── notebooks/
├── requirements.txt
├── setup.py
└── README.md
```

## Run

1. Create virtual environment: `python -m venv .venv`
2. Activate: `.venv\Scripts\activate`
3. Install: `pip install -r requirements.txt`
4. Configure: Copy `.env.example` to `.env` and set values (or set `ENVIRONMENT`/`YAML_FILE_NAME` directly)
5. Run a job:
   ```sh
   python -m src.main --job-code DAD_REPORT_TIME_TABLE_HUB
   ```

Optional example with overrides:

```sh
python -m src.main --job-code DAD_REPORT_TIME_TABLE_HUB \
  --schedule-type daily \
  --reference-date 2026-05-20 \
  --output-format xlsx
```

Optional overrides supported by the runner:

```sh
python -m src.main --job-code DAD_REPORT_TIME_TABLE_HUB \
  --schedule-type daily \
  --reference-date 2026-05-20 \
  --output-format xlsx
```

**CLI Parameters:**
- `--job-code` : Keep as `DAD_REPORT_TIME_TABLE_HUB`
- `--schedule-type` : Override schedule (`daily` / `weekly` / `monthly`)
- `--reference-date` : Override date (`YYYY-MM-DD`)
- `--output-format` : Output format (`xlsx` / `csv`)

## Time Table Hub Flow (Simplified)

1. Load query manifest for `delivery.sql` and `pickup.sql`.
2. Inject `STARTDATE` and `ENDDATE` parameters from schedule range.
3. Run delivery and pickup SQL in parallel using dedicated DB connections.
4. Apply grouping keys from ETL KTR logic:
   `date`, `hour`, `zone_code`, `uz_pickup`, `uz_delivery`, `opcode`, `activity`.
5. Compute `count_awb` as row count of `awb` per group and sort by grouping keys.
6. Export a combined Excel file with two sheets: `Delivery` and `Pickup`.
7. Save output locally as `DAD_REPORT_TIME_TABLE_HUB_YYYYMMDD.xlsx` in `REPORT.FILE_PATH`.
8. Skip SharePoint upload by default (local testing mode).

To re-enable upload later, set `REPORT.ENABLE_UPLOAD=true` in your active YAML config.

## Adding a New Job

## Config Files

The active YAML file is selected by `ENVIRONMENT` and `YAML_FILE_NAME` in `.env`.

Available config files in this repo:

- `config/config/local.yaml`
- `config/config/arif.yaml`
- `config/config/dev_andre.yaml`
- `config/config/email_template.jinja2`

Notes:

- `local.yaml` is the default local development config.
- `EMAIL.ENABLED` is read at runtime by the HUB job.
- `REPORT.ENABLE_UPLOAD` controls whether upload/email logic runs.

## HUB Job Notes

The job implementation is in [src/jobs/dad_report_time_table_hub.py](src/jobs/dad_report_time_table_hub.py).

Important runtime details:

- `JOB_REGISTRY` in [src/main.py](src/main.py) contains only `DAD_REPORT_TIME_TABLE_HUB`.
- The job uses `src/sql/time_table_hub/manifest.json` and the SQL files under `src/sql/time_table_hub/`.
- Output filename is generated in the job code, not from the old multi-job templates.
- Email recipients are hardcoded in the job, while SMTP credentials are read from `analysis_services.config_process_switch`.

## Validation

Quick syntax check:

```sh
python -m compileall src
```

If you want to inspect the current job behavior, start from:

- [src/main.py](src/main.py)
- [src/jobs/dad_report_time_table_hub.py](src/jobs/dad_report_time_table_hub.py)
- [docs/jobs/dad_report_time_table_hub.md](docs/jobs/dad_report_time_table_hub.md)
