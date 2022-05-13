from iicActor.utils.job import IICJob


class AgJob(IICJob):
    """ Placeholder which link the data request with the required resources and mhs commands. """

    def __init__(self, iicActor, seqObj, visitSetId):
        IICJob.__init__(self, iicActor=iicActor, seqObj=seqObj, visitSetId=visitSetId)

        self.basicResources = ['ag']
        self.dependencies = seqObj.dependencies

    def __str__(self):
        return f'AgJob(resources={",".join(self.required)} visit={self.seq.visitStart} ' \
               f'startedAt({self.tStart.datetime.isoformat()}) ' \
               f'active={not self.seq.isDone} didFail=({self.seq.didFail}, {self.seq.output})'
