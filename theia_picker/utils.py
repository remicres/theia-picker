"""
This module contains some helpers.
"""
import logging
import os

logging.basicConfig(level=os.environ.get("LOGLEVEL") or "INFO")
log = logging.getLogger("theia-picker")

hide_progress = os.environ.get("THEIAPICKER_HIDE_PROGRESS")
