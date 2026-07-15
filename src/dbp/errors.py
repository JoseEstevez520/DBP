"""DBP error hierarchy.

All exceptions raised by the Data Boundary Protocol implementation
derive from :class:`DBPError` so callers can catch the entire family
with a single ``except DBPError`` clause.
"""


class DBPError(Exception):
    """Base exception for all DBP errors."""


class EmptyClearanceError(DBPError):
    """Raised when an empty set of compartments is used to build a Clearance."""


class LabelViolationError(DBPError):
    """Raised when a boundary check fails and the caller treats BLOCK as fatal."""


class InvalidMessageError(DBPError):
    """Raised when a DBPMessage cannot be constructed or parsed due to missing/invalid fields."""


class BoundaryCheckError(DBPError):
    """Raised when the boundary engine encounters an internal error during a check."""
