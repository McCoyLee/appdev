import sys

from loguru import logger

from .config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stdout,
        level=settings.app_log_level,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level:<7}</level> | "
            "<cyan>{name}:{function}:{line}</cyan> | "
            "{message}"
        ),
        colorize=True,
    )
