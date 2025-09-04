"""
Improved logging configuration for cleaner output.
Reduces noise and eliminates duplicate entries.
"""

import logging
import sys
from typing import Set

class DeduplicatingHandler(logging.StreamHandler):
    """Custom handler that prevents duplicate log messages"""
    
    def __init__(self, stream=None):
        super().__init__(stream)
        self._seen_messages: Set[str] = set()
        self._max_seen_size = 1000
    
    def emit(self, record):
        message_key = f"{record.levelname}:{record.name}:{record.getMessage()}"
        
        if message_key in self._seen_messages:
            return
            
    
        self._seen_messages.add(message_key)
        if len(self._seen_messages) > self._max_seen_size:
           
            self._seen_messages = set(list(self._seen_messages)[500:])
        
        super().emit(record)

def setup_logging():
    """Configure all loggers for cleaner output"""
    
    
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    
  
    main_handler = DeduplicatingHandler(sys.stdout)
    main_handler.setFormatter(formatter)
    main_handler.setLevel(logging.INFO)
    

    main_loggers = [
        "outbound-caller",
        "everest_fleet_logs", 
        "agent.helper.entrypoint_handler",
        "agent.helper.call_handlers",
        "agent.helper.database_helpers"
    ]
    
    for logger_name in main_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.addHandler(main_handler)
        logger.propagate = False
    

    transcript_logger = logging.getLogger("transcript")
    transcript_logger.setLevel(logging.INFO)
    transcript_logger.handlers.clear()
    transcript_handler = logging.StreamHandler(sys.stdout)
    transcript_formatter = logging.Formatter('%(message)s')
    transcript_handler.setFormatter(transcript_formatter)
    transcript_logger.addHandler(transcript_handler)
    transcript_logger.propagate = False
    
    noisy_loggers = [
        "openai", "httpx", "httpcore", "botocore", "boto3", 
        "s3transfer", "urllib3", "asyncio", "livekit.agents.llm",
        "livekit.agents.stt", "livekit.agents.tts", "livekit.agents.vad",
        "livekit.plugins.turn_detector",  
        "call-logger", 
        "db-manager"   
    ]
    
    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.ERROR) 
        logger.propagate = False
    
    livekit_logger = logging.getLogger("livekit")
    livekit_logger.setLevel(logging.ERROR)
    

    important_livekit_loggers = ["livekit.agents"]
    for logger_name in important_livekit_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
    

    root_logger.setLevel(logging.INFO)
    
    return logging.getLogger("outbound-caller"), transcript_logger

def get_logger(name: str = "outbound-caller") -> logging.Logger:
    """Get a configured logger instance"""
    return logging.getLogger(name)

def get_transcript_logger() -> logging.Logger:
    """Get the transcript logger instance"""
    return logging.getLogger("transcript")


def log_once(logger: logging.Logger, level: int, message: str, key: str = None):
    """Log a message only once using a unique key"""
    if not hasattr(log_once, '_seen_keys'):
        log_once._seen_keys = set()
    
    log_key = key or message
    if log_key not in log_once._seen_keys:
        log_once._seen_keys.add(log_key)
        logger.log(level, message)