from actorcore.QThread import QThread
from astropy import time as astroTime
from ics.iicActor import visit
from ics.utils.threading import threaded
from ics.iicActor.utils.lib import wait

from opscore.utility.qstr import qstr


class IICJob(QThread):
    def __init__(self, iicActor, seqObj, visitSetId):
        self.tStart = astroTime.Time.now()
        QThread.__init__(self, iicActor, str(self.tStart))

        self.visitor = visit.VisitManager(iicActor)
        self.seqObj = seqObj
        self.visitSetId = visitSetId

        self.basicResources = []
        self.dependencies = []

    @property
    def resources(self):
        return list(map(str, self.basicResources + self.dependencies))

    @property
    def required(self):
        return list(map(str, self.basicResources + self.activeDependencies))

    @property
    def activeDependencies(self):
        return self.dependencies

    @property
    def isDone(self):
        return self.seq.isDone

    @threaded
    def fire(self, cmd):
        """ Put Job on the Thread. """
        self.seq.process(cmd)
        cmd.finish()

    def genStatus(self, cmd):
        """ Process the sequence in the Job's thread as it would behave in the main one. """
        cmd.inform(f"seq{self.visitSetId}={qstr(self)}")
        cmd.inform(self.seq.genKeys())

    def free(self):
        """ Make sure, you aren't leaving anything behind. """
        self.seq.clear()
        self.seq = None
        self.exit()

    def instantiate(self, cmd, *args, **kwargs):
        """ Instantiate seqObj with given args, kwargs. """
        self.seq = self.seqObj(*args, **kwargs)
        self.seq.assign(cmd, self)

    def abort(self, cmd):
        """ Make sure, you aren't leaving anything behind. """
        self.seq.abort(cmd)

        while not self.isDone:
            wait()

        self.genStatus(cmd)

    def finish(self, cmd, **kwargs):
        """ Make sure, you aren't leaving anything behind. """
        self.seq.finish(cmd, **kwargs)

        while not self.isDone:
            wait()

        self.genStatus(cmd)

    def sanityCheck(self, cmd):
        pass

    def handleTimeout(self):
        """ Called when the .get() times out. Intended to be overridden. """
        pass
