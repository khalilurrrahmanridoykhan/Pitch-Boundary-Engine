import logging

import pytest


@pytest.fixture(autouse=True)
def reset_pipeline_logger():
    """configure_logging() changes global logger state; undo it after every test."""
    yield
    logger = logging.getLogger("pitch_engine")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
