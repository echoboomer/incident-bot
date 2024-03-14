class ConfigurationError(Exception):
    """Exception raised for errors in a config object

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class IndexNotFoundError(Exception):
    """Exception raised for index not found

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class PostmortemException(Exception):
    """Exceptions raised during postmortem creation"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)
