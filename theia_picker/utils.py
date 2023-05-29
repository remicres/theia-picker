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
    """
    Returns a progressbar for the iterable object if the environment variable
    THEIAPICKER_HIDE_PROGRESS is not set.

    Args:
        iterable_object: iterable object
        *args: args
        **kwargs: keyword args

    Returns:
        iterable object

    """
    return iterable_object if hide_progress \
        else tqdm(*args, **kwargs)
