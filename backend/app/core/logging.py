import logging
import sys
from pythonjsonlogger import jsonlogger


def setup_logging(level: str = "INFO") -> None:
    """
    Configure un logger JSON structuré, compatible avec tout agrégateur
    (Loki, CloudWatch, Datadog…).
    """
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
