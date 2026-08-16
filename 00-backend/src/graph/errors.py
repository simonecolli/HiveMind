class DebateStopped(Exception):
    """Raised when the user asks for the debate to stop.

    A plain `Exception` rather than task cancellation on purpose: `CancelledError`
    is a `BaseException`, so the handler that records the session outcome would
    not catch it and the session would stay `running` for ever.
    """
