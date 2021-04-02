from importlib import reload

import ics.iicActor.sps.sequence as spsSequence
import ics.iicActor.sps.timed as timedSpsSequence
from actorcore.QThread import QThread
from astropy import time as astroTime
from ics.iicActor import visit
from iicActor.utils.lib import process
from opscore.utility.qstr import qstr
from pfs.utils.sps.config import SpsConfig

reload(spsSequence)
reload(timedSpsSequence)


class SpectroJob(QThread):
    """ Placeholder which link the data request with the required resources and mhs commands. """

    def __init__(self, iicActor, identKeys, seqObj):
        self.tStart = astroTime.Time.now()
        self.isFirstVisitor = True
        QThread.__init__(self, iicActor, 'toto')
        specs = SpsConfig.fromModel(self.actor.models['sps']).identify(**identKeys)
        self.isDone = False
        self.visitor = visit.VisitManager(iicActor)
        self.seqObj = seqObj
        self.visitSetId = self.getVisit(isFirstVisitor=False)

        self.lightSource = self.getLightSource(specs) if seqObj.lightBeam else None
        self.specs = specs
        self.dependencies = list(set(sum([spec.dependencies(seqObj) for spec in specs], [])))

    @property
    def basicResources(self):
        return list(filter(None, [self.lightSource] + self.specs))

    @property
    def activeDependencies(self):
        active = self.dependencies if self.lightSource is not None else []
        return active

    @property
    def resources(self):
        return list(map(str, self.basicResources + self.dependencies))

    @property
    def required(self):
        return list(map(str, self.basicResources + self.activeDependencies))

    @property
    def camNames(self):
        return list(map(str, self.specs))

    def getStatus(self, doShort=True):
        if not self.isDone:
            return 'active'

        if self.seq.status in ['complete', 'finishRequested']:
            status = 'finished'
        elif self.seq.status == 'abortRequested':
            status = 'aborted'
        else:
            status = 'failed' if doShort else self.seq.status

        return status

    def __str__(self):
        return f'SpectroJob(lightSource={self.lightSource} resources={",".join(self.required)} ' \
               f'visitRange={self.seq.visitStart},{self.seq.visitEnd} startedAt({self.tStart.datetime.isoformat()}) ' \
               f'status={self.getStatus(doShort=False)}'

    def getLightSource(self, specs):
        """ Get light source from our sets of specs. """
        try:
            [light] = list(set([spec.lightSource for spec in specs]))
        except:
            raise RuntimeError('there can only be one light source for a given sequence')

        return light

    def isInFocus(self, cmd):
        """ Check that the camera(s) are indeed in focus. """
        ret = self.actor.cmdr.call(actor='sps', cmdStr=f'checkFocus cams={",".join(self.camNames)}', forUserCmd=cmd,
                                   timeLim=10)

        if ret.didFail:
            for reply in ret.replyList:
                cmd.warn(reply.keywords.canonical(delimiter=';'))
            return False

        return True

    def instantiate(self, cmd, *args, **kwargs):
        """ Instantiate seqObj with given args, kwargs. """
        self.seq = self.seqObj(cams=self.camNames, *args, **kwargs)
        self.seq.assign(cmd, self)

    @process
    def fire(self, cmd):
        """ Put Job on the Thread. """
        self.seq.process(cmd)

    def genStatus(self, cmd):
        """ Process the sequence in the Job's thread as it would behave in the main one. """
        cmd.inform(f"seq{self.visitSetId}={qstr(self)}")
        cmd.inform(self.seq.genKeys())

    def getVisit(self, isFirstVisitor=None):
        """ Get visit, make sure visitSetId=first visit. """
        isFirstVisitor = self.isFirstVisitor if isFirstVisitor is None else isFirstVisitor

        if isFirstVisitor:
            self.isFirstVisitor = False
            visit = self.visitSetId
        else:
            ourVisit = self.visitor.newVisit('sps')
            visit = ourVisit.visitId

        return visit

    def releaseVisit(self):
        """ Release visit. """
        self.visitor.releaseVisit()

    def free(self):
        """ Make sure, you aren't leaving anything behind. """
        self.seq.clear()
        self.seq = None
        self.exit()

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

    def genIdentKeys(self, cmdKeys):
        """ Identify which spectrograph(cameras) is required to take data. """
        keys = dict()
        if 'cam' in cmdKeys and ('sm' in cmdKeys or 'arm' in cmdKeys):
            raise RuntimeError('you cannot provide both cam and (sm or arm)')

        for key in ['cam', 'arm', 'sm']:
            # to be removed later on
            tkey = 'cams' if key == 'cam' else key
            keys[tkey] = cmdKeys[key].values if key in cmdKeys else None

        return keys

    def request(self, cmd, seqObj):
        """ Request a new Job and lock it if all checks passes. """
        identKeys = self.genIdentKeys(cmd.cmd.keywords)
        job = SpectroJob(self.actor, identKeys, seqObj)

        if any([resource in self.busy for resource in job.resources]):
            raise RuntimeError('cannot fire your sequence, dependent resources already busy...')

        if any([resource in self.locked for resource in job.required]):
            raise RuntimeError('cannot fire your sequence, required resources already locked...')

        if seqObj.doCheckFocus and not job.isInFocus(cmd):
            raise RuntimeError('Spectrograph is not in focus...')

        return self.lock(job)

    def lock(self, job):
        """ all specs points to the same job. """
        # for spec in job.specs:
        #     self.allocate(job, key=spec.camName)
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

    def identify(self, identifier, lightSource=True):
        """ identify jon from identifier(sps, dcb ...), look for job with light source first. """
        ret = None

        if isinstance(identifier, int):
            visitSetId = identifier
            try:
                return self.jobs[visitSetId]
            except KeyError:
                raise RuntimeError(f'{visitSetId} is not valid, activeSequences:{self.activeSequences}')

        for job in set(self.jobs.values()):
            if (lightSource and job.lightSource is None) or job.isDone:
                continue

            if identifier == 'sps':
                if all([spec.specModule.spsModule for spec in job.specs]):
                    ret = job

            elif identifier in ['dcb', 'dcb2', 'sunss']:
                if all([spec.lightSource == identifier for spec in job.specs]):
                    ret = job
            else:
                raise RuntimeError('unknown identifier')

        if ret is None and lightSource:
            return self.identify(identifier=identifier, lightSource=False)

        if ret is None:
            raise RuntimeError('could not identify job')

        return ret

    def finish(self, cmd, identifier='sps', **kwargs):
        """ finish an on going job. """
        job = self.identify(identifier=identifier)
        if job.isDone:
            raise RuntimeError('job already finished')

        cmd.inform(f'text="finalizing exposure from sequence(id:{job.visitSetId})..."')
        job.seq.finish(cmd, **kwargs)
        return job

    def abort(self, cmd, identifier='sps'):
        """ abort an on going job. """
        job = self.identify(identifier=identifier)
        if job.isDone:
            raise RuntimeError('job already finished')

        cmd.inform(f'text="aborting exposure from sequence(id:{job.visitSetId})..."')
        job.seq.abort(cmd)
        return job

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
