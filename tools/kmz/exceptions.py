"""Domain-specific exceptions for the KMZ toolkit."""


class KmzError(Exception):
    """Base class for KMZ toolkit errors."""


class EmojiRenderError(KmzError):
    """Raised when an emoji cannot be turned into a pin icon."""


class VenueDataError(KmzError):
    """Raised when source venue data is missing or malformed."""
