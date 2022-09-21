import ics.iicActor.sps.engineering as spsEngineering
from astropy import time as astroTime
from ics.iicActor.ag.job import AgJob
from ics.iicActor.ag.sequence import AgSequence
from ics.iicActor.fps.job import FpsJob
from ics.iicActor.fps.sequence import FpsSequence
from ics.iicActor.sps.job import SpectroJob, RdaJob
from ics.iicActor.sps.sequence import SpsSequence
from ics.utils.opdb import opDB
from ics.utils.sps.config import SpsConfig
from iicActor.utils.lib import genIdentKeys


class ResourceManager(object):
    """ Placeholder to reject/accept incoming jobs based on the availability of the software/hardware. """

    def __init__(self, actor):
        self.actor = actor
        self.groupIds = dict()
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

        elif issubclass(seqObj, AgSequence):
            job = AgJob(self.actor, seqObj, visitSetId)

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

        if identifier is None:
            try:
                [ret] = [job for job in self.jobs.values() if not job.isDone]
            except:
                pass

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
        newVisitSetId = max(lastVisitSetId + self.activeIds + list(self.groupIds.values())) + 1
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

    def requestGroupId(self, groupName, doContinue=False):
        """"""
        # just return the current one.
        if doContinue:
            if groupName not in self.groupIds.keys():
                raise KeyError(f'no group:{groupName} is actually on-going !')

            return self.groupIds[groupName]

        # reserving a visit_set_id/group_id
        groupId = self.arrangeVisitSetId()
        self.groupIds[groupName] = groupId
        return groupId
