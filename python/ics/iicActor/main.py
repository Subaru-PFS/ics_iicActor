#!/usr/bin/env python3

import os

import actorcore.ICC
import iicActor.utils.mergePfsDesign as merge
import iicActor.utils.pfsDesign as pfsDesignUtils
import numpy as np
import pandas as pd
import pfs.utils.pfsConfigUtils as pfsConfigUtils
from ics.iicActor.utils.pfsDesign import PfsDesignHandler
from ics.utils.sps.spectroIds import getSite
from iicActor.utils import engine
from iicActor.utils import keyBuffer
from pfs.datamodel.pfsConfig import PfsDesign, TargetType
from pfs.utils.fiberids import FiberIds
from twisted.internet import reactor


class IicActor(actorcore.ICC.ICC):
    def __init__(self, name,
                 productName=None,
                 debugLevel=30):
        """ Setup an Actor instance. See help for actorcore.Actor for details. """

        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name,
                                   productName=productName,
                                   modelNames=['hub', 'sps'])

        # No quite sure what to do about this yet. But one of the
        # "clocks" of the PFS is the single visit, for which the IIC
        # is responsible for distributing to sub actors.
        #
        self.site = None
        self.engine = engine.Engine(self)
        self.buffer = keyBuffer.KeyBuffer(self)

        self.everConnected = False

    @property
    def visitManager(self):
        return self.engine.visitManager

    def connectionMade(self):
        if self.everConnected is False:
            self.logger.info('Establishing first tron connection...')
            self.everConnected = True

            _needModels = [self.name, 'gen2', 'fps', 'mcs', 'ag', 'dcb', 'dcb2', 'sunss']
            self.logger.info(f'adding models: {sorted(_needModels)}')
            self.addModels(_needModels)
            self.logger.info(f'added models: {sorted(self.models.keys())}')

            self.site = getSite()
            self.logger.info(f'site :{self.site}')

            for spectrographId in range(1, 5):
                self.addModels([f'enu_sm{spectrographId}'])
                self.buffer.attachCallback('sps', f'sm{spectrographId}LightSource', self.genPfsDesign)

            for dcb in {'dcb', 'dcb2'}:
                self.buffer.attachCallback(dcb, 'designId', self.genPfsDesign)

            self.models['fps'].keyVarDict['pfsConfig'].addCallback(self.fpsConfig)

            reactor.callLater(1, self.letsGetReadyToRumble)

    def letsGetReadyToRumble(self):
        """"""
        for actor in ['hub', 'sps', 'dcb', 'dcb2']:
            self.cmdr.bgCall(callFunc=None, actor=actor, cmdStr='status')

    def fpsConfig(self, keyVar):
        """Callback called whenever fps.pfsConfig is generated."""
        try:
            designId, visit0, status = keyVar.getValue()
        except ValueError:
            return

        self.logger.info(f'fpsConfig={designId},{visit0},{status}')

        if status == 'Done' and self.visitManager.activeField:
            self.visitManager.activeField.loadPfsConfig0(designId, visit0)

    def genPfsDesign(self, cmd=None):
        """Called from sps.smXLightSource or dcb.designId callbacks, this reset the current field and attempt to
        regenerate a new design file based on the current config."""
        cmd = self.bcast if cmd is None else cmd
        # clearing pfsField
        self.visitManager.finishField()
        self.genPfsDesignKey(cmd)
        # merge design from current setup, no merging for pfi/fps for now.
        designId, designed_at = self.mergePfsDesignFromCurrentSetup()
        # genVisit0 if a fps.convergence is expected.
        genVisit0 = 'pfi' in self.buffer.lightSources
        # declaring and loading a new PfsDesign.
        self.visitManager.declareNewField(designId, genVisit0=genVisit0)
        # Ingest design.
        pfsDesignUtils.PfsDesignHandler.ingest(cmd, self.visitManager.getField().pfsDesign,
                                               designed_at=designed_at, to_be_observed_at='now')
        self.genPfsDesignKey(cmd)

    def mergePfsDesignFromCurrentSetup(self):
        """ Merge design given the current setup, there are basically two modes :
        When pfi is the only lightSource, in that case pfsDesignId is declared by users.
        When SuNSS &| DCB &| DCB2 are the light sources, since they are static, it can be generated automatically."""

        def genAutoDesign():
            """Generate a merged PfsDesign when SuNSS, DCB, DCB2 are connected to different spectrographs."""

            def pfsDesignDirName(lightSource):
                return os.path.join(self.actorConfig['pfsDesign']['rootDir'], lightSource)

            gfm = pd.DataFrame(FiberIds().data)
            designToMerge = []
            designNames = []

            for specInd, lightSource in enumerate(self.buffer['lightSources']):
                spectrographId = specInd + 1
                # adding engineering fibers.
                engDesign = PfsDesign.read(0xfacefeeb, pfsDesignDirName('engFibers'))
                designToMerge.append(engDesign[engDesign.spectrograph == spectrographId])

                if lightSource == 'none':
                    designNames.append('None')
                    continue  # just adding engineering fibers in that case.

                elif lightSource == 'sunss':
                    designNames.append('SuNSS.0xdeadbeef')
                    pfsDesign = PfsDesign.read(0xdeadbeef, pfsDesignDirName(lightSource))
                    fiberHoleId = gfm[gfm.fiberId.isin(pfsDesign.fiberId)].fiberHoleId
                    allSpectro = gfm[gfm.fiberHoleId.isin(fiberHoleId)]
                    fiberId = allSpectro.query(f'spectrographId=={spectrographId}').fiberId.to_numpy().astype('int32')
                    pfsDesign.fiberId = fiberId
                    pfsDesign.objId = fiberId

                elif lightSource in {'dcb', 'dcb2'}:
                    designId = self.models[lightSource].keyVarDict['designId'].getValue()
                    designNames.append(f'{lightSource}.0x{designId:016x}')
                    pfsDesign = PfsDesign.read(designId, pfsDesignDirName(lightSource))
                    pfsDesign = pfsDesign[pfsDesign.spectrograph == spectrographId]
                    pfsDesign.targetType = np.repeat(TargetType.DCB, len(pfsDesign)).astype('int32')

                else:
                    raise ValueError(f'cannot merge design for {lightSource}')

                designToMerge.append(pfsDesign)

            return merge.mergeSuNSSAndDcbDesign(designToMerge, designName=','.join(designNames))

        designed_at = None

        # no merging for pfi
        if 'pfi' in self.buffer.lightSources:
            designId = self.actorData.loadKey('fpsDesignId')
            return designId, designed_at

        # Proceed and generate the design automatically.
        mergedDesign = genAutoDesign()
        # Check if designFile already exists.
        if not os.path.isfile(os.path.join(self.actorConfig['pfsDesign']['rootDir'], mergedDesign.filename)):
            designed_at = 'now'
            mergedDesign.write(self.actorConfig['pfsDesign']['rootDir'])

        return mergedDesign.pfsDesignId, designed_at

    def declareFpsDesign(self, cmd, designId=None, variant=0):
        """"""
        cmdKeys = cmd.cmd.keywords
        designId = cmdKeys['designId'].values[0] if designId is None else designId
        variant = cmdKeys['variant'].values[0] if 'variant' in cmdKeys else variant

        # get actual pfsDesignId from designId0 and variant.
        if variant:
            designId = PfsDesignHandler.designIdFromVariant(designId0=designId, variant=variant)

        # persist fps.pfsDesignId
        self.actorData.persistKey('fpsDesignId', designId)

        return self.genPfsDesign(cmd)

    def genPfsDesignKey(self, cmd):
        """"""
        activeField = self.visitManager.activeField
        designId = 0 if activeField is None else activeField.pfsDesign.pfsDesignId
        visit0 = 0 if activeField is None else activeField.visit0
        raBoresight = np.NaN if activeField is None else activeField.pfsDesign.raBoresight
        decBoresight = np.NaN if activeField is None else activeField.pfsDesign.decBoresight
        posAng = np.NaN if activeField is None else activeField.pfsDesign.posAng
        designName = 'None' if activeField is None else activeField.pfsDesign.designName
        designId0 = 0 if activeField is None else activeField.pfsDesign.designId0
        variant = 0 if activeField is None else activeField.pfsDesign.variant

        # still generating that key for header/drp for now.
        cmd.inform('designId=0x%016x' % designId)
        cmd.inform('pfsDesign=0x%016x,%d,%.6f,%.6f,%.6f,"%s",0x%016x,%d' % (designId,
                                                                            visit0,
                                                                            raBoresight,
                                                                            decBoresight,
                                                                            posAng,
                                                                            designName,
                                                                            designId0,
                                                                            variant))

    def genPfsConfigKey(self, cmd, pfsConfig):
        """"""
        cmd.inform('pfsConfig=0x%016x,%d,"%s",%.6f,%.6f,%.6f,"%s",0x%016x,%d' % (pfsConfig.pfsDesignId,
                                                                                 pfsConfig.visit,
                                                                                 pfsConfigUtils.getDateDir(pfsConfig),
                                                                                 pfsConfig.raBoresight,
                                                                                 pfsConfig.decBoresight,
                                                                                 pfsConfig.posAng,
                                                                                 pfsConfig.designName,
                                                                                 pfsConfig.designId0,
                                                                                 pfsConfig.variant))


def main():
    theActor = IicActor('iic', productName='iicActor')
    theActor.run()


if __name__ == '__main__':
    main()
