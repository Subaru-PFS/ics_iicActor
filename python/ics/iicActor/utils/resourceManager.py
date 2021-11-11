import ics.iicActor.sps.engineering as spsEngineering
from actorcore.QThread import QThread
from astropy import time as astroTime
from ics.iicActor import visit
from ics.iicActor.fps.job import FpsJob
from ics.iicActor.fps.sequence import FpsSequence
from ics.iicActor.sps.job import SpectroJob, RdaJob
from ics.iicActor.sps.sequence import SpsSequence
from ics.utils.opdb import opDB
from ics.utils.sps.config import SpsConfig
from ics.utils.threading import threaded
from iicActor.utils.lib import wait, genIdentKeys
from opscore.utility.qstr import qstr


class IICJob(QThread):
    def __init__(self, iicActor, seqObj, visitSetId):
        self.tStart = astroTime.Time.now()
        QThread.__init__(self, iicActor, str(self.tStart))

        self.isDone = False
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


class ResourceManager(object):
    """ Placeholder to reject/accept incoming jobs based on the availability of the software/hardware. """

    def __init__(self, actor):
        self.actor = actor
        self.jobs = dict()

    @property
    def onGoing(self):
        return [job for job in self.jobs.values() if not job.isDone]

    @property
    def activeIds(self):
        return [job.visitSetId for job in self.onGoing]

    @property
    def activeSequences(self):
        activeSequences = ",".join(map(str, self.activeIds))
        activeSequences = 'None' if not activeSequences else activeSequences
        return activeSequences

    @property
    def busy(self):
        return sum([job.required for job in self.onGoing], [])

    @property
    def locked(self):
        return sum([job.resources for job in self.onGoing], [])

    def request(self, cmd, seqObj):
        """ Request a new Job and lock it if all checks passes. """
        visitSetId = self.arrangeVisitSetId()

        if issubclass(seqObj, SpsSequence):
            identKeys = genIdentKeys(cmd.cmd.keywords)
            specs = SpsConfig.fromModel(self.actor.models['sps']).identify(**identKeys)
            job = SpectroJob(self.actor, specs, seqObj, visitSetId)

        elif issubclass(seqObj, FpsSequence):
            job = FpsJob(self.actor, seqObj, visitSetId)

        elif issubclass(seqObj, spsEngineering.RdaMove):
            identKeys = genIdentKeys(cmd.cmd.keywords)
            specModules = SpsConfig.fromModel(self.actor.models['sps']).selectModules(identKeys['sm'])
            job = RdaJob(self.actor, specModules, seqObj, visitSetId)

        else:
            raise RuntimeError('unknown sequence type')

        if any([resource in self.busy for resource in job.resources]):
            raise RuntimeError('cannot fire your sequence, dependent resources already busy...')

        if any([resource in self.locked for resource in job.required]):
            raise RuntimeError('cannot fire your sequence, required resources already locked...')

        job.sanityCheck(cmd)

        return self.lock(job)

    def lock(self, job):
        """ all specs points to the same job. """
        self.allocate(job, job.visitSetId)

        return job

    def allocate(self, job, key):
        """ Just associate a spec with a job, free a previous job if it's not longer referenced. """
        try:
            prevJob = self.jobs[key]
        except KeyError:
            prevJob = None

        self.jobs[key] = job

        if prevJob is not None and prevJob not in self.jobs.values():
            prevJob.free()

        self.cleanHistory()

    def cleanHistory(self, nDay=1):
        """ Just associate a spec with a job, free a previous job if it's not longer referenced. """
        now = float(astroTime.Time.now().mjd)
        oldVisitSets = [job.visitSetId for job in self.jobs.values() if now - job.tStart.mjd > nDay]

        for visitSetId in oldVisitSets:
            self.jobs[visitSetId].free()
            self.jobs.pop(visitSetId, None)

    def identify(self, identifier):
        """ identify job from identifier(sps, dcb ...), look for job with light source first. """
        ret = None

        if isinstance(identifier, int):
            visitSetId = identifier
            try:
                return self.jobs[visitSetId]
            except KeyError:
                raise RuntimeError(f'{visitSetId} is not valid, activeSequences:{self.activeSequences}')

        for job in set(self.jobs.values()):
            if job.isDone:
                continue

            if identifier == 'sps':
                if isinstance(job, SpectroJob) and all([spec.specModule.spsModule for spec in job.specs]):
                    ret = job

            if identifier == 'fps':
                if isinstance(job, FpsJob):
                    ret = job

        if ret is None:
            raise RuntimeError('could not identify job')

        return ret

    def fetchLastVisitSetId(self):
        """ get last visit_set_id from opDB """
        visit_set_id, = opDB.fetchone('select max(visit_set_id) from iic_sequence')
        visit_set_id = 0 if visit_set_id is None else visit_set_id
        return int(visit_set_id)

    def arrangeVisitSetId(self):
        """ Multiple Jobs can happen in parallel, make sure you don't attribute same visit_set_id.  """
        lastVisitSetId = [self.fetchLastVisitSetId()]
        newVisitSetId = max(lastVisitSetId + self.activeIds) + 1
        return newVisitSetId

    def genStatus(self, cmd, visitSetId=None):
        """ generate Job(s) status(es). """

        if visitSetId is not None:
            try:
                job = self.jobs[visitSetId]
                return job.genStatus(cmd)
            except KeyError:
                raise RuntimeError(f'{visitSetId} is not valid, valids:{",".join(map(str, self.jobs.keys()))}')

        cmd.inform(f'activeSequences={self.activeSequences}')

        for job in self.jobs.values():
            job.genStatus(cmd)
