from importlib import reload

import ics.iicActor.sps.sequence as spsSequence
import ics.iicActor.sps.timed as timedSpsSequence
from actorcore.QThread import QThread
from ics.iicActor import visit
from opdb import utils, opdb
from opscore.utility.qstr import qstr
from pfs.utils.spsConfig import SpsConfig

reload(spsSequence)
reload(timedSpsSequence)


class SpectroJob(QThread):
    """ Placeholder which link the data request with the required resources and mhs commands. """

    def __init__(self, iicActor, identKeys, seqObj, visitSetId):
        QThread.__init__(self, iicActor, 'toto')
        self.isProcessed = False
        self.visitor = visit.VisitManager(iicActor)
        self.specs = SpsConfig.fromModel(iicActor.models['sps']).identify(**identKeys)
        self.seqObj = seqObj
        self.visitSetId = visitSetId

        self.lightSource = self.getLightSource(self.specs) if seqObj.lightBeam else None
        self.resources = list(set(sum([spec.assessResources(seqObj) for spec in self.specs], [])))

    @property
    def camNames(self):
        return [spec.camName for spec in self.specs]

    @property
    def required(self):
        return [r for r in self.resources if r.required]

    @property
    def locked(self):
        return [r for r in self.resources if not r.required]

    def __str__(self):
        return f'SpectroJob(lightSource={self.lightSource} required={",".join(self.required)} locked={",".join(self.locked)} finished={self.isProcessed})'

    def getLightSource(self, specs):
        """ Get light source from our sets of specs(camera). """
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

    def fire(self, cmd):
        """ Put Job on the Thread. """
        self.start()
        self.putMsg(self.process, cmd=cmd)

    def process(self, cmd):
        """ Process the sequence in the Job's thread as it would behave in the main one. """
        try:
            self.seq.process(cmd)

        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))
            return

        finally:
            self.isProcessed = True

        cmd.finish()

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
        return [job for job in self.jobs.values() if not job.isProcessed]

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

    def request(self, cmd, seqObj, doCheckFocus=False):
        """ Request a new Job and lock it if all checks passes. """
        identKeys = self.genIdentKeys(cmd.cmd.keywords)
        visitSetId = self.arrangeVisitSetId()
        job = SpectroJob(self.actor, identKeys, seqObj, visitSetId)

        if any([resource in self.busy for resource in job.resources]):
            raise RuntimeError('cannot fire your sequence, required resources already busy...')

        if any([resource in self.locked for resource in job.required]):
            raise RuntimeError('cannot fire your sequence, required resources already locked...')

        if doCheckFocus and not job.isInFocus(cmd):
            raise RuntimeError('text="Spectrograph is not in focus...')

        return self.lock(job)

    def lock(self, job):
        """ all specs points to the same job. """
        for spec in job.specs:
            self.allocate(job, key=spec.camName)

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

    def fetchLastVisitSetId(self):
        """ get last visit_set_id from opDB """
        df = utils.fetch_query(opdb.OpDB.url, 'select max(visit_set_id) from sps_sequence')
        visit_set_id, = df.loc[0].values
        visit_set_id = 0 if visit_set_id is None else visit_set_id
        return int(visit_set_id)

    def arrangeVisitSetId(self):
        """ Multiple Jobs can happen in parallel, make sure you don't attribute same visit_set_id.  """
        lastVisitSetId = self.fetchLastVisitSetId() + 1
        aliveVisitSetId = [job.visitSetId for job in self.jobs.values()]
        visitSetId = max(aliveVisitSetId) + 1 if lastVisitSetId in aliveVisitSetId else lastVisitSetId
        return visitSetId

    def getStatus(self, cmd):
        """ generate Job(s) status(es). """
        for job in list(set(self.jobs.values())):
            cmd.inform(f"text={qstr(job)}")
