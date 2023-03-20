"""
This module contains some helpers.
"""
import os
import logging
logging.basicConfig(level=os.environ.get("LOGLEVEL") or "INFO")
log = logging.getLogger("theia-picker")
