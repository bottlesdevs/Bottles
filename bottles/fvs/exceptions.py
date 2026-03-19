class FVSException(Exception):
    pass

class FVSNothingToCommit(FVSException):
    pass

class FVSNothingToRestore(FVSException):
    pass

class FVSStateNotFound(FVSException):
    pass

class FVSStateZeroNotDeletable(FVSException):
    pass

class FVSStateAlreadyExists(FVSException):
    pass

class FVSMissingStateIndex(FVSException):
    pass

class FVSEmptyStateIndex(FVSException):
    pass
