import logging

from app.logging_config import configure_logging
from app.main import main

configure_logging("INFO")
logger = logging.getLogger(__name__)
logger.info("startup: launching bot")
main()
