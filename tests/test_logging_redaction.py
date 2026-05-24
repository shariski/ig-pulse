"""The access token must never reach the logs (CLAUDE.md B2).

httpx logs full request URLs at INFO, and our Graph API URLs carry
``?access_token=...`` — so configure_logging() must mute the httpx logger.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.main import configure_logging


def test_httpx_logger_muted_to_keep_token_out_of_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "logs_dir", tmp_path)
    logging.getLogger("httpx").setLevel(logging.NOTSET)  # start from a clean slate

    configure_logging()

    # At INFO, httpx emits "HTTP Request: GET <url-with-access_token> ...".
    # Muting it to WARNING keeps the token out of logs/ig_pulse.log.
    assert logging.getLogger("httpx").level == logging.WARNING
