"""
This module contains some helpers.
"""
import logging
import os
from tqdm.autonotebook import tqdm

logging.basicConfig(level=os.environ.get("LOGLEVEL") or "INFO")
log = logging.getLogger("theia-picker")

hide_progress = os.environ.get("THEIAPICKER_HIDE_PROGRESS")


# progress bar
def progressbar(iterable_object, *args, **kwargs):
    return iterable_object if hide_progress \
        else tqdm(*args, **kwargs)
