# backend/app/core/logging.py
#For debugging

import logging
import sys
from logging.config import dictConfig

def setup_logging():
    """
    Logging for debugging!
      - Uvicorn logs and FastAPI logs are unified
      - Logs print to stdout
    """

    LOGGING_CONFIG = {
        "version": 1,
        "disable_existing_loggers": False,

        "formatters": {
            "default": {
                "format": "%(levelname)s [%(asctime)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "uvicorn": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(message)s",
                "use_colors": True,
            },
        },

        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "default",
            },
            "uvicorn": {
                "class": "logging.StreamHandler",
                "stream": sys.stdout,
                "formatter": "uvicorn",
            },

        },

        "loggers": {
            "": {  
                #root logger
                "handlers": ["console"],
                "level": "INFO",
            },
            "app": {
                "handlers": ["console"],
                "level": "DEBUG",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["uvicorn"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.error": {
                "handlers": ["uvicorn"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    dictConfig(LOGGING_CONFIG)
