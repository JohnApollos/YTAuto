class AutonomousMediaError(Exception):
    pass

class ModelTimeoutError(AutonomousMediaError):
    pass

class MalformedOutputError(AutonomousMediaError):
    pass

class StageUnrecoverableError(AutonomousMediaError):
    pass

class QuotaExceededError(AutonomousMediaError):
    pass

class RightsBlockedError(AutonomousMediaError):
    pass
