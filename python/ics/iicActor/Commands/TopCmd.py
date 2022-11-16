from importlib import reload

import iicActor.utils.pfsDesign as pfsDesignUtils
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from pfs.utils.pfsDesignVariants import makeVariantDesign

reload(pfsDesignUtils)
PfsDesignHandler = pfsDesignUtils.PfsDesignHandler


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

            ('declareCurrentPfsDesign', '<designId> [<variant>]', self.declareCurrentPfsDesign),
            ('createVariants', '[<nVariants>] [<addVariants>] [<designId0>] [<sigma>]', self.createVariants),
            ('getAllVariants', '<designId0>', self.getAllVariants),

            ('finishField', '', self.finishField),
            ('ingestPfsDesign', '<designId> [<designedAt>] [<toBeObservedAt>]', self.ingestPfsDesign),

            ('visit0', '@(freeze|unfreeze) <caller>', self.setVisit0)
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('designId', types.Long(), help='selected pfsDesignId'),
                                        keys.Key('designId0', types.Long(), help='selected pfsDesignId0'),

                                        keys.Key('variant', types.Int(), help='selected pfsDesign variant'),
                                        keys.Key('nVariants', types.Int(), help='number of variants to be created'),
                                        keys.Key('addVariants', types.Int(), help='number of variants to be added'),
                                        keys.Key('sigma', types.Float(), help='sigma for random position noise'),

                                        keys.Key('caller', types.String(), help='visit caller'),
                                        keys.Key('designedAt', types.String(), help=''),
                                        keys.Key('toBeObservedAt', types.String(), help=''),
                                        )

    @property
    def engine(self):
        return self.actor.engine

    @property
    def visitManager(self):
        return self.engine.visitManager

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
        pfsDesign, visit0 = PfsDesignHandler.declareCurrent(cmd, self.visitManager)

        # setting grating to design.
        self.actor.cmdr.bgCall(None, 'iic', 'setGratingToDesign')

        # generating keyword for gen2
        designName = 'unnamed' if not pfsDesign.designName else pfsDesign.designName
        try:
            designId0 = pfsDesign.designId0
            variant = pfsDesign.variant
        except AttributeError:
            designId0 = 0
            variant = 0

        cmd.finish('pfsDesign=0x%016x,%d,%.6f,%.6f,%.6f,"%s",0x%016x,%d' % (pfsDesign.pfsDesignId,
                                                                            visit0,
                                                                            pfsDesign.raBoresight,
                                                                            pfsDesign.decBoresight,
                                                                            pfsDesign.posAng,
                                                                            designName,
                                                                            designId0,
                                                                            variant))

    def createVariants(self, cmd):
        cmdKeys = cmd.cmd.keywords

        sigma = cmdKeys['sigma'].values[0] if 'sigma' in cmdKeys else 1
        designId0 = cmdKeys['designId0'].values[
            0] if 'designId0' in cmdKeys else self.engine.visitManager.getCurrentDesignId()

        if 'nVariants' in cmdKeys:
            # make sure no variants already exist.
            if PfsDesignHandler.getAllVariants(designId0).size:
                cmd.fail('text="there is already variants matching that designId0, use addVariants instead."')
                return
            # variant starts at 1.
            variants = np.array(list(range(cmdKeys['nVariants'].values[0]))) + 1

        elif 'addVariants' in cmdKeys:
            maxVariant = PfsDesignHandler.maxVariantMatchingDesignId0(designId0)
            variants = np.array(list(range(cmdKeys['addVariants'].values[0]))) + maxVariant + 1

        else:
            cmd.fail('text="either nVariants or addVariants must be specified."')
            return

        # Reading design0 file.
        pfsDesign0 = PfsDesignHandler.read(designId0, dirName=self.actor.actorConfig['pfsDesign']['rootDir'])

        for variant in variants:
            cmd.inform(f'text="creating variant {variant} for designId0 {designId0}"')
            pfsDesignVariant = makeVariantDesign(pfsDesign0, variant=variant, sigma=sigma)
            # writing to disk
            pfsDesignVariant.write(dirName=self.actor.actorConfig['pfsDesign']['rootDir'])
            # Ingesting into opdb.
            PfsDesignHandler.ingest(cmd, pfsDesignVariant, designed_at='now', to_be_observed_at='now')

        cmd.finish()

    def getAllVariants(self, cmd):
        """"""
        cmdKeys = cmd.cmd.keywords

        designId0 = cmdKeys['designId0'].values[0]
        allVariants = PfsDesignHandler.getAllVariants(designId0)

        if not allVariants.size:
            cmd.fail(f'text="havent found any variant matching designId0:0x%016x'%designId0)
            return

        for designId, variant in allVariants:
            cmd.inform(f'text="designId0:0x%016x found variant %d designId:0x%016x'%(designId0, variant, designId))

        cmd.finish()

    def finishField(self, cmd):
        """Report camera status and actor version. """
        # invalidating previous pfsDesign keyword
        self.visitManager.finishField()

        cmd.finish('pfsDesign=0x%016x,%d,%.6f,%.6f,%.6f,"%s",0x%016x,%d' % (0,
                                                                            0,
                                                                            np.NaN,
                                                                            np.NaN,
                                                                            np.NaN,
                                                                            'none',
                                                                            0,
                                                                            0)
                   )

    def ingestPfsDesign(self, cmd):
        """Report camera status and actor version. """
        cmdKeys = cmd.cmd.keywords

        designId = cmdKeys['designId'].values[0]
        designed_at = cmdKeys['designedAt'].values[0] if 'designedAt' in cmdKeys else None
        to_be_observed_at = cmdKeys['toBeObservedAt'].values[0] if 'toBeObservedAt' in cmdKeys else None
        # Reading design file.
        pfsDesign = PfsDesignHandler.read(designId,
                                          dirName=self.actor.actorConfig['pfsDesign']['rootDir'])
        # Ingesting into opdb.
        PfsDesignHandler.ingest(cmd, pfsDesign,
                                designed_at=designed_at, to_be_observed_at=to_be_observed_at)

        cmd.finish()

    def setVisit0(self, cmd):
        """Add more control over how visit0 is handled."""
        cmdKeys = cmd.cmd.keywords

        caller = cmdKeys['caller'].values[0]
        doFreeze = 'unfreeze' not in cmdKeys

        # get matching visit.
        visit = self.visitManager.getField().getVisit(caller)

        cmd.inform(f'text="freezing({doFreeze} visit0({visit.visitId}) for {caller}')
        visit.setFrozen(doFreeze)

        cmd.finish()
