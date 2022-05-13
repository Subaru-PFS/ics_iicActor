import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
import pfs.utils.ingestPfsDesign as ingestPfsDesign
from ics.utils.opdb import opDB


class TopCmd(object):

    def __init__(self, actor):
        # This lets us access the rest of the actor.
        self.actor = actor

        # Declare the commands we implement. When the actor is started
        # these are registered with the parser, which will call the
        # associated methods when matched. The callbacks will be
        # passed a single argument, the parsed and typed command.
        #
        self.vocab = [
            ('ping', '', self.ping),
            ('status', '', self.status),
            ('declareCurrentPfsDesign', '<designId>', self.declareCurrentPfsDesign),
            ('finishField', '', self.finishField)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('designId', types.Long(), help='selected pfsDesignId')
                                        )

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""

        cmd.warn("text='I am an empty and fake actor'")
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version. """

        self.actor.sendVersionKey(cmd)
        cmd.finish()

    def declareCurrentPfsDesign(self, cmd):
        """Report camera status and actor version. """
        cmdKeys = cmd.cmd.keywords
        pfsDesignId = cmdKeys['designId'].values[0]

        # declaring new field
        pfsDesign, visit0 = self.actor.visitor.declareNewField(pfsDesignId)

        # inserting into opdb
        newDesign = not opDB.fetchone(
            f'select pfs_design_id from pfs_design where pfs_design_id={pfsDesign.pfsDesignId}')
        if newDesign:
            ingestPfsDesign.ingestPfsDesign(pfsDesign, to_be_observed_at='now')
        else:
            cmd.warn('text="pfsDesign(0x%016x) already inserted in opdb..."' % pfsDesign.pfsDesignId)

        # setting grating to design.
        self.actor.callCommand('setGratingToDesign')

        # generating keyword for gen2
        designName = 'unnamed' if not pfsDesign.designName else pfsDesign.designName
        cmd.finish('pfsDesign=0x%016x,%d,%.6f,%.6f,%.6f,%s' % (pfsDesign.pfsDesignId,
                                                               visit0.visitId,
                                                               pfsDesign.raBoresight,
                                                               pfsDesign.decBoresight,
                                                               pfsDesign.posAng,
                                                               designName))

    def finishField(self, cmd):
        """Report camera status and actor version. """
        # invalidating previous pfsDesign keyword
        self.actor.visitor.finishField()

        cmd.finish('pfsDesign=0x%016x,%d,%.6f,%.6f,%.6f,%s' % (0,
                                                               0,
                                                               np.NaN,
                                                               np.NaN,
                                                               np.NaN,
                                                               'none'))
