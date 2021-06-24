from iicActor.utils.resource import IICJob


class SpectroJob(IICJob):
    """ Placeholder which link the data request with the required resources and mhs commands. """

    def __init__(self, iicActor, specs, seqObj, visitSetId):
        IICJob.__init__(self, iicActor=iicActor, seqObj=seqObj, visitSetId=visitSetId)

        self.lightSource = self.getLightSource(specs) if seqObj.lightBeam else None
        self.specs = specs

        self.basicResources = list(filter(None, [self.lightSource] + self.specs))
        self.dependencies = list(set(sum([spec.dependencies(seqObj) for spec in specs], [])))

    @property
    def activeDependencies(self):
        active = self.dependencies if self.lightSource is not None else []
        return active

    @property
    def camNames(self):
        return list(map(str, self.specs))

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

    def sanityCheck(self, cmd):
        if self.seqObj.doCheckFocus and not self.isInFocus(cmd):
            raise RuntimeError('Spectrograph is not in focus...')

    def instantiate(self, cmd, *args, **kwargs):
        """ Instantiate seqObj with given args, kwargs. """
        self.seq = self.seqObj(cams=self.camNames, *args, **kwargs)
        self.seq.assign(cmd, self)
