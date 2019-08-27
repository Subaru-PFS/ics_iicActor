class VisitActiveError(Exception):
    pass

class VisitNotActiveError(Exception):
    pass

class VisitManager(object):
    def newVisit(self, name=None):
        """ Allocate a new visit. """

class Visit(object):
    def __init__(self):
        self._fetchFromGen2()

    def _fetchFromGen2(self):
        raise NotImplementedError()

    def frameForAGC(self):
        raise NotImplementedError()

    def frameForFPS(self):
        raise NotImplementedError()
