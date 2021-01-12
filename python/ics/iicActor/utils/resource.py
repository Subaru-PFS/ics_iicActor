from importlib import reload

import ics.iicActor.sps.sequence as spsSequence
import ics.iicActor.sps.timed as timedSpsSequence
from ics.iicActor.utils.sequencing import SubCmd
from actorcore.QThread import QThread
from pfs.utils.spsConfig import SpsConfig
from opscore.utility.qstr import qstr

reload(spsSequence)
reload(timedSpsSequence)


class SpectroJob(QThread):
    def __init__(self, iicActor, identKeys, seqObj):
        self.seqObj = seqObj
        self.specs = SpsConfig.fromModel(iicActor.models['sps']).identify(**identKeys)

        self.lightSource = self.getLightSource(self.specs) if seqObj.lightRequired else None
        self.enus = list(set([spec.enu for spec in self.specs]))
        self.isProcessed = False

        QThread.__init__(self, iicActor, 'toto')

    @property
    def camNames(self):
        return [spec.camName for spec in self.specs]

    @property
    def requiredParts(self):
        parts = self.camNames + self.enus if self.lightSource is not None else self.camNames
        return parts

    @property
    def requiredResources(self):
        return list(filter(None, [self.lightSource] + self.requiredParts))

    def __str__(self):
        return f'SpectroJob(lightSource={self.lightSource} locked={",".join(self.requiredParts)})'

    def getLightSource(self, specs):
        try:
            [light] = list(set([spec.lightSource for spec in specs]))
        except:
            raise RuntimeError('there can only be one light source for a given sequence')

        return light

    def isInFocus(self, cmd):
        ret = self.actor.cmdr.call(actor='sps', cmdStr=f'checkFocus cams={",".join(self.camNames)}', forUserCmd=cmd,
                                   timeLim=10)

        if ret.didFail:
            for reply in ret.replyList:
                cmd.warn(reply.keywords.canonical(delimiter=';'))
            return False

        return True

    def instantiate(self, cmd, *args, **kwargs):
        self.seq = self.seqObj(cams=self.camNames, *args, **kwargs)
        self.seq.register(cmd, iicActor=self.actor)

    def fire(self, cmd):
        self.start()
        self.process(cmd)

    def process(self, cmd):

        try:
            self.seq.process(cmd)

        except Exception as e:
            cmd.fail('text=%s' % self.actor.strTraceback(e))
            return

        finally:
            self.isProcessed = True

        cmd.finish()

    def free(self):
        self.exit()

    def handleTimeout(self):
        pass


class ResourceManager(object):
    def __init__(self, actor):
        self.actor = actor
        self.jobs = dict()

    @property
    def onGoing(self):
        return [job for job in self.jobs.values() if not job.isProcessed]

    @property
    def locked(self):
        return sum([job.requiredResources for job in self.onGoing], [])

    def genIdentKeys(self, cmdKeys):
        keys = dict()
        if 'cam' in cmdKeys and ('sm' in cmdKeys or 'arm' in cmdKeys):
            raise RuntimeError('you cannot provide both cam and (sm or arm)')

        for key in ['cam', 'arm', 'sm']:
            #to be removed later on
            tkey = 'cams' if key == 'cam' else key
            keys[tkey] = cmdKeys[key].values if key in cmdKeys else None

        return keys

    def request(self, cmd, seqObj, doCheckFocus=False):
        identKeys = self.genIdentKeys(cmd.cmd.keywords)
        job = SpectroJob(self.actor, identKeys, seqObj)

        if any([resource in self.locked for resource in job.requiredResources]):
            raise RuntimeError('cannot fire your sequence, required resources already locked...')

        if doCheckFocus and not job.isInFocus(cmd):
            raise RuntimeError('text="Spectrograph is not in focus...')

        return self.lock(job)

    def lock(self, job):
        if job.lightSource is None:
            for spec in job.specs:
                self.allocate(job, key=spec.camName)
        else:
            self.allocate(job, key=job.lightSource)

        return job

    def allocate(self, job, key):
        try:
            prevJob = self.jobs[key]
        except KeyError:
            prevJob = None

        self.jobs[key] = job

        if prevJob is not None and prevJob not in self.jobs:
            prevJob.free()



    def getStatus(self, cmd):
        for job in list(set(self.jobs.values())):
            cmd.inform(f"text={qstr(job)}")
