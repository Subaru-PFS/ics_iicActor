from iicActor.utils.job import IICJob


class FpsJob(IICJob):
    """ Placeholder which link the data request with the required resources and mhs commands. """

    def __init__(self, iicActor, seqObj, visitSetId):
        IICJob.__init__(self, iicActor=iicActor, seqObj=seqObj, visitSetId=visitSetId)

        self.basicResources = ['fps']
        self.dependencies = seqObj.dependencies

    def __str__(self):
        return f'FpsJob(resources={",".join(self.required)} visit={self.seq.visitStart} ' \
               f'startedAt({self.tStart.datetime.isoformat()}) status={self.getStatus(doShort=False)}'
