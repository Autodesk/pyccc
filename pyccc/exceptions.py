class ProgramFailure(Exception):
    pass


class TimeoutError(Exception):
    """ This job's status is not "Finshed" or "Error"
    """
    pass


class JobStillRunning(Exception):
    """ Raised when a job's status is not "Finshed" or "Error"
    """
    pass


class EngineTestError(Exception):
    """ Raised when an engine fails basic connection tests

    Args:
        engine (pyccc.engines.base.EngineBase): the little engine that couldn't
    """
    def __init__(self, engine):
        super(EngineTestError, self).__init__('Failed to run jobs on Engine: %s' % engine)


class DockerMachineError(Exception):
    """ Failures related to connecting to docker machines
    """