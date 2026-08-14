from enum import Enum, auto


class StartupStatus(Enum):
    """
    Represents the current state of the application during the bootstrap lifecycle.
    """
    NOT_STARTED = auto()
    INITIALIZING = auto()
    READY = auto()
    FAILED = auto()
