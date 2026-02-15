"""Custom exceptions for the application."""


class CancellationError(Exception):
    """Raised when a job is cancelled."""

    def __init__(self, message: str = "Job was cancelled"):
        self.message = message
        super().__init__(self.message)


class DownloadError(Exception):
    """Raised when audio download fails."""

    def __init__(self, message: str = "Download failed"):
        self.message = message
        super().__init__(self.message)


class TranscriptionError(Exception):
    """Raised when transcription fails."""

    def __init__(self, message: str = "Transcription failed"):
        self.message = message
        super().__init__(self.message)


class ValidationError(Exception):
    """Raised when validation fails."""

    def __init__(self, message: str = "Validation failed"):
        self.message = message
        super().__init__(self.message)


class TradingError(Exception):
    """Raised when a trading operation fails."""

    def __init__(self, message: str = "Trading operation failed"):
        self.message = message
        super().__init__(self.message)
