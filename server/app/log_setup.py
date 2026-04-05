import logging
from collections import deque
import threading
from typing import Callable, Any, Optional

class MemoryLogHandler(logging.Handler):
    def __init__(self, capacity: int = 100):
        super().__init__()
        self.capacity = capacity
        self.logs = deque(maxlen=capacity)
        self._memory_lock = threading.RLock()
        self.on_log: Optional[Callable[[dict[str, Any]], None]] = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if self.formatter:
                timestamp = self.formatter.formatTime(record, self.formatter.datefmt)
            else:
                timestamp = logging.Formatter().formatTime(record)
            
            entry = {
                "timestamp": timestamp,
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "formatted": msg
            }
            with self._memory_lock:
                self.logs.append(entry)
            
            if self.on_log:
                self.on_log(entry)
        except Exception as e:
            self.handleError(record)

    def get_recent_logs(self) -> list[dict[str, Any]]:
        with self._memory_lock:
            return list(self.logs)

memory_handler = MemoryLogHandler()
