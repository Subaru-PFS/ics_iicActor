from importlib import reload

import iicActor.utils.pfsDesign as pfsDesignUtils
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types

reload(pfsDesignUtils)


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
            ('ingestPfsDesign', '<designId> [<designedAt>] [<toBeObservedAt>]', self.ingestPfsDesign),
            ('finishField', '', self.finishField),
            ('visit0', '@(freeze|unfreeze) <caller>', self.setVisit0)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('designId', types.Long(), help='selected pfsDesignId'),
                                        keys.Key('caller', types.String(), help='visit caller'),
                                        keys.Key('designedAt', types.String(), help=''),
                                        keys.Key('toBeObservedAt', types.String(), help=''),
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
        pfsDesign, visit0 = pfsDesignUtils.PfsDesignHandler.declareCurrent(cmd, self.actor.visitor)

        # setting grating to design.
        self.actor.callCommand('setGratingToDesign')

        # generating keyword for gen2
        designName = 'unnamed' if not pfsDesign.designName else pfsDesign.designName
        cmd.finish('pfsDesign=0x%016x,%d,%.6f,%.6f,%.6f,%s' % (pfsDesign.pfsDesignId,
                                                               visit0,
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

    def setVisit0(self, cmd):
        """Add more control over how visit0 is handled."""
        cmdKeys = cmd.cmd.keywords

        caller = cmdKeys['caller'].values[0]
        doFreeze = 'unfreeze' not in cmdKeys

        # get matching visit.
        visit = self.actor.visitor.getField().getVisit(caller)

        cmd.inform(f'text="freezing({doFreeze} visit0({visit.visitId}) for {caller}')
        visit.setFrozen(doFreeze)

        cmd.finish()

    def ingestPfsDesign(self, cmd):
        """Report camera status and actor version. """
        cmdKeys = cmd.cmd.keywords

        designId = cmdKeys['designId'].values[0]
        designed_at = cmdKeys['designedAt'].values[0] if 'designedAt' in cmdKeys else None
        to_be_observed_at = cmdKeys['toBeObservedAt'].values[0] if 'toBeObservedAt' in cmdKeys else None
        # Reading design file.
        pfsDesign = pfsDesignUtils.PfsDesignHandler.read(designId,
                                                         dirName=self.actor.actorConfig['pfsDesign']['rootDir'])
        # Ingesting into opdb.
        pfsDesignUtils.PfsDesignHandler.ingest(cmd, pfsDesign,
                                               designed_at=designed_at, to_be_observed_at=to_be_observed_at)

        cmd.finish()
