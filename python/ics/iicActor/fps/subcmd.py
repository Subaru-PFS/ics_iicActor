from ics.iicActor.utils.subcmd import VisitedCmd
from ics.utils.opdb import opDB
from ics.utils.cmd import cmdVarToKeys


class FpsCmd(VisitedCmd):
    """ Placeholder to handle dcb command specificities"""

    def __init__(self, cmdStr, timeLim=120, **kwargs):
        VisitedCmd.__init__(self, 'fps', cmdStr, timeLim=timeLim, **kwargs)


class MoveToPfsDesignCmd(VisitedCmd):
    """ Placeholder to handle dcb command specificities"""

    def __init__(self, designId, timeLim=120, **kwargs):
        VisitedCmd.__init__(self, 'fps', f'moveToPfsDesign designId={designId}', timeLim=timeLim, **kwargs)
        self.designId = designId

    def getVisit(self):
        """ Get visit from ics.iicActor.visit.Visit """
        ourVisit = self.iicActor.visitor.declareNewField(designId=self.designId)
        return ourVisit.visitId

    def pfsConfigIsValid(self, cmdVar):
        """ Get visit from ics.iicActor.visit.Visit """
        cmdKeys = cmdVarToKeys(cmdVar)

        try:
            pfsConfigId = cmdKeys['pfsConfigId'].values[0]
        except:
            pfsConfigId = False

        return pfsConfigId

    def releaseVisit(self, cmdVar):
        """ Release visit """
        VisitedCmd.releaseVisit(self)

        if not self.pfsConfigIsValid(cmdVar):
            self.iicActor.visitor.resetVisit0()

        if self.iicActor.visitor.validVisit0:
            opDB.insert('field_set', visit_set_id=self.sequence.visit_set_id, visit0=self.iicActor.visitor.visit0.visitId)
