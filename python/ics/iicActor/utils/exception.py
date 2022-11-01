from ics.iicActor.utils.lib import stripQuotes


class IicException(Exception):
    def __init__(self, reason="", className=""):
        self.reason = reason
        self.className = className
        Exception.__init__(self)

    def __str__(self):
        className = self.__class__.__name__ if not self.className else self.className
        return f"{className}({self.reason})"


class ResourceUnAvailable(IicException):
    """Exception raised when exposure is just trash and needs to be cleared ASAP."""


class ResourceIsBusy(IicException):
    """Exception raised when exposure is just trash and needs to be cleared ASAP."""


class OpDBFailure(IicException):
    """Exception raised when exposure is just trash and needs to be cleared ASAP."""


class SequenceIdentificationFailure(IicException):
    """Exception raised when exposure is just trash and needs to be cleared ASAP."""


class SequenceAborted(IicException):
    """Exception raised when exposure is just trash and needs to be cleared ASAP."""


class OpdbInsertFailed(IicException):
    """Exception raised when exposure is just trash and needs to be cleared ASAP."""

    def __init__(self, tableName, reason):
        self.tableName = tableName
        self.reason = stripQuotes(str(reason))
        Exception.__init__(self)

    def __str__(self):
        return f"{self.__class__.__name__}({self.tableName}) with {self.reason})"


class Failures(list):
    def add(self, reason):
        if 'SequenceAborted(' in reason and self.format():
            pass  # something else causes the failure
        else:
            self.append(reason)

    def format(self):
        return ','.join(list(set(self)))
