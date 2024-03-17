from importlib import reload

import iicActor.utils.pfsDesign.opdb as designDB
import numpy as np
import opscore.protocols.keys as keys
import opscore.protocols.types as types
from pfs.datamodel import PfsDesign
from pfs.utils.pfsDesignVariants import makeVariantDesign

reload(designDB)


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
            ('createVariants', '[<nVariants>] [<addVariants>] [<designId0>] [<sigma>] [<randomFraction>] [@(doHex)]',
             self.createVariants),
            ('getAllVariants', '<designId0>', self.getAllVariants),
            ('getMaxVariants', '<designId0>', self.getMaxVariants),

            ('finishField', '', self.finishField),
            ('ingestPfsDesign', '<designId> [<designedAt>] [<toBeObservedAt>]', self.ingestPfsDesign),
        ]

        # Define typed command arguments for the above commands.
        self.keys = keys.KeysDictionary("iic_iic", (1, 1),
                                        keys.Key('designId', types.Long(), help='selected pfsDesignId'),
                                        keys.Key('designId0', types.Long(), help='selected pfsDesignId0'),

                                        keys.Key('variant', types.Int(), help='selected pfsDesign variant'),
                                        keys.Key('nVariants', types.Int(), help='number of variants to be created'),
                                        keys.Key('addVariants', types.Int(), help='number of variants to be added'),
                                        keys.Key('sigma', types.Float(), help='sigma for random position noise'),
                                        keys.Key('randomFraction', types.Float(), help='fraction of cobras set to random position'),

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

    @property
    def pfsDesignRootDir(self):
        return self.actor.actorConfig['pfsDesign']['rootDir']

    def ping(self, cmd):
        """Query the actor for liveness/happiness."""
        cmd.finish("text='Present and (probably) well'")

    def status(self, cmd):
        """Report camera status and actor version."""
        self.actor.sendVersionKey(cmd)
        self.actor.genPfsDesignKey(cmd)

        cmd.finish()

    def declareCurrentPfsDesign(self, cmd):
        """Declare current FpsDesignId, note that if only pfi is connected FpsDesignId==PfsDesignId."""
        self.actor.declareFpsDesign(cmd)

        # setting grating to design.
        self.actor.cmdr.bgCall(None, 'iic', 'setGratingToDesign')

        cmd.finish()

    def finishField(self, cmd):
        """Reset current PfsField."""
        # invalidating previous pfsDesign keyword
        self.visitManager.finishField()
        self.actor.genPfsDesignKey(cmd)

        cmd.finish()

    def createVariants(self, cmd):
        """Create PfsDesign variants given a designId0."""
        cmdKeys = cmd.cmd.keywords

        sigma = cmdKeys['sigma'].values[0] if 'sigma' in cmdKeys else 1
        randomFraction = cmdKeys['randomFraction'].values[0] if 'randomFraction' in cmdKeys else 1
        doHex = 'doHex' in cmdKeys
        designId0 = cmdKeys['designId0'].values[0] if 'designId0' in cmdKeys else self.visitManager.getCurrentDesignId()

        if 'nVariants' in cmdKeys:
            # make sure no variants already exist.
            if designDB.getAllVariants(designId0).size:
                cmd.fail('text="there is already variants matching that designId0, use addVariants instead."')
                return
            # variant starts at 1.
            variants = np.array(list(range(cmdKeys['nVariants'].values[0]))) + 1

        elif 'addVariants' in cmdKeys:
            maxVariant = designDB.maxVariantMatchingDesignId0(designId0)
            variants = np.array(list(range(cmdKeys['addVariants'].values[0]))) + maxVariant + 1

        else:
            cmd.fail('text="either nVariants or addVariants must be specified."')
            return

        # Reading design0 file.
        pfsDesign0 = PfsDesign.read(designId0, dirName=self.pfsDesignRootDir)

        for variant in variants:
            cmd.inform(f'text="creating variant {variant} for designId0 0x{designId0:016x}"')
            pfsDesignVariant = makeVariantDesign(pfsDesign0, variant=variant, sigma=sigma, doHex=doHex,
                                                 randomFraction=randomFraction)
            # writing to disk
            pfsDesignVariant.write(dirName=self.pfsDesignRootDir)
            # Ingesting into opdb.
            designDB.ingest(cmd, pfsDesignVariant, designed_at='now', to_be_observed_at='now')

        cmd.finish()

    def getAllVariants(self, cmd):
        """Get all variant PfsDesign(nVariant,designId) given a designId0."""
        cmdKeys = cmd.cmd.keywords

        designId0 = cmdKeys['designId0'].values[0]
        allVariants = designDB.getAllVariants(designId0)

        if not allVariants.size:
            cmd.fail(f'text="have not found any variants matching designId0 0x{designId0:016x}"')
            return

        for designId, variant in allVariants:
            cmd.inform(f'text="designId0 0x{designId0:016x} found variant {variant} designId 0x{designId0:016x}"')

        cmd.finish()

    def getMaxVariants(self, cmd):
        """Get max nVariant PfsDesign(nVariant,designId) given a designId0."""
        cmdKeys = cmd.cmd.keywords

        designId0 = cmdKeys['designId0'].values[0]
        allVariants = designDB.getAllVariants(designId0)

        if not allVariants.size:
            cmd.fail(f'text="have not found any variants matching designId0 0x{designId0:016x}"')
            return

        maxVariant = np.max(allVariants[:, 1])

        cmd.finish(f'text="designId0 0x{designId0:016x} maxVariant={maxVariant}"')

    def ingestPfsDesign(self, cmd):
        """Load and ingest a PfsDesign into opdb given a pfsDesignId."""
        cmdKeys = cmd.cmd.keywords

        designId = cmdKeys['designId'].values[0]
        designed_at = cmdKeys['designedAt'].values[0] if 'designedAt' in cmdKeys else None
        to_be_observed_at = cmdKeys['toBeObservedAt'].values[0] if 'toBeObservedAt' in cmdKeys else None
        # Reading design file.
        pfsDesign = PfsDesign.read(designId, dirName=self.pfsDesignRootDir)
        # Ingesting into opdb.
        designDB.ingest(cmd, pfsDesign, designed_at=designed_at, to_be_observed_at=to_be_observed_at)

        cmd.finish()
