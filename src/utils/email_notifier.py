"""
Email notifier – send HTML emails via SMTP.

Uses Jinja2 templates for the HTML body and sends via SMTP
with credentials stored in ``analysis_services.config_process_switch``.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


def render_template(template_path: str, context: Dict) -> str:
    """
    Render a Jinja2 HTML template with *context* variables.

    Parameters
    ----------
    template_path : str
        Relative or absolute path to the ``.jinja2`` file.
    context : dict
        Variables available inside the template (e.g. ``report_date``,
        ``file_link``, ``report_title``).

    Returns
    -------
    str – rendered HTML.
    """
    template_dir = os.path.dirname(os.path.abspath(template_path))
    template_name = os.path.basename(template_path)

    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True,
    )
    tpl = env.get_template(template_name)
    return tpl.render(**context)


def _parse_emails(addr_str: Optional[str]) -> List[str]:
    """Split a comma/semicolon/space-separated address string into a list."""
    if not addr_str:
        return []
    return [a.strip() for a in addr_str.replace(";", " ").replace(",", " ").split() if a.strip()]


def send_email(
    subject: str,
    body_html: str,
    to_email: Optional[str] = None,
    cc_email: Optional[str] = None,
    bcc_email: Optional[str] = None,
    from_email: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: int = 587,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """
    Send an email via SMTP.

    Parameters
    ----------
    subject, body_html
        Email subject and pre-rendered HTML body.
    to_email, cc_email, bcc_email
        Space/comma/semicolon-separated addresses.
    from_email : str
        Sender address in RFC 5322 format, e.g. 'Display Name <addr>'.
    smtp_host : str
        SMTP server hostname.
    smtp_port : int
        SMTP server port (default 587 for STARTTLS).
    username, password
        SMTP authentication credentials.
    """
    to_list = _parse_emails(to_email)
    cc_list = _parse_emails(cc_email)
    bcc_list = _parse_emails(bcc_email)
    all_recipients = to_list + cc_list + bcc_list

    if not all_recipients:
        logger.warning("No recipients specified – skipping email")
        return

    if not from_email:
        raise ValueError("from_email is required")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg.attach(MIMEText(body_html, "html"))

    logger.info(
        f"Sending email via SMTP ({smtp_host}:{smtp_port}): "
        f"from={from_email} subject='{subject}' to={to_email}"
    )

    with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
        server.starttls()
        server.login(username, password)
        server.sendmail(from_email, all_recipients, msg.as_string())

    logger.info("Email sent successfully via SMTP")


def send_report_email(
    template_path: str,
    to_email: Optional[str],
    cc_email: Optional[str] = None,
    bcc_email: Optional[str] = None,
    subject: str = "Report",
    context: Optional[Dict] = None,
    from_email: Optional[str] = None,
    smtp_host: Optional[str] = None,
    smtp_port: int = 587,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """
    Convenience wrapper: render Jinja2 template + send via SMTP.

    *context* is passed straight to the Jinja2 template.
    Typical keys: ``report_date``, ``report_title``, ``file_link``,
    ``file_name``, ``schedule_type``.
    """
    body_html = render_template(template_path, context or {})
    send_email(
        subject=subject,
        body_html=body_html,
        to_email=to_email,
        cc_email=cc_email,
        bcc_email=bcc_email,
        from_email=from_email,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=username,
        password=password,
    )
