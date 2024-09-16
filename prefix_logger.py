import logging
from typing import Any, Optional, List

'''
PrefixLogger: Enforces hierarchical logging structure.
- Wraps logging.getLogger("name") and forwards calls to it.
- Use get_child("suffix") to create loggers with automatic prefixing.
- Pass PrefixLogger instances to objects for consistent hierarchy.

Example:
    logger = PrefixLogger("app")
    child_logger = logger.get_child("Component")
    child_logger.info("Message")  # Logs as "app.Component: Message"
'''
class PrefixLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.logger.critical(msg, *args, **kwargs)

    def get_child(self, suffix: str) -> 'PrefixLogger':
        #ensures the child has the current name as prefix
        #as long the logger name is used as prefix
        new_name = f"{self.name}.{suffix}"
        return PrefixLogger(new_name)

def setup_logger() -> PrefixLogger:
    return PrefixLogger("awrtc")
