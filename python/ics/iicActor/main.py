#!/usr/bin/env python3

import os

import actorcore.ICC
import ics.iicActor.utils.pfsDesign.opdb as designDB
import iicActor.utils.pfsDesign.merge as mergeDesign
import numpy as np
import pandas as pd
from ics.utils.sps.spectroIds import getSite
from iicActor.utils import engine
from iicActor.utils import keyBuffer
from pfs.datamodel.pfsConfig import PfsDesign, TargetType
from pfs.utils.fiberids import FiberIds
from pfs.utils.pfsConfigUtils import getDateDir
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

    @property
    def spsConfig(self):
        return self.engine.resourceManager.spsConfig

    @property
    def pfiConnected(self):
        return 'pfi' in self.buffer.lightSources

    @property
    def scrLightsOn(self):
        status = self.models['scr'].keyVarDict['scrLights'].getValue()
        return status == 'on'

    def connectionMade(self):
        if self.everConnected is False:
            self.logger.info('Establishing first tron connection...')
            self.everConnected = True

            _needModels = [self.name, 'gen2', 'fps', 'mcs', 'ag', 'dcb', 'dcb2', 'sunss', 'scr']
            self.logger.info(f'adding models: {sorted(_needModels)}')
            self.addModels(_needModels)
            self.logger.info(f'added models: {sorted(self.models.keys())}')

            self.site = getSite()
            self.logger.info(f'site :{self.site}')

            for spectrographId in range(1, 5):
                enuActor = f'enu_sm{spectrographId}'
                self.addModels([enuActor])
                self.buffer.attachCallback('sps', f'sm{spectrographId}LightSource', self.genPfsDesign)
                self.models[enuActor].keyVarDict['redResolution'].addCallback(self.engine.resourceManager.freeEnu)

            for dcb in {'dcb', 'dcb2'}:
                self.buffer.attachCallback(dcb, 'designId', self.genPfsDesign)

            self.models['fps'].keyVarDict['pfsConfig'].addCallback(self.fpsConfig)
            self.models['sps'].keyVarDict['fiberIllumination'].addCallback(self.updateFiberIllumination)

            reactor.callLater(1, self.letsGetReadyToRumble)

    def letsGetReadyToRumble(self):
        """"""
        for actor in ['hub', 'sps', 'dcb', 'dcb2']:
            self.cmdr.bgCall(callFunc=None, actor=actor, cmdStr='status')

    def genPfsDesign(self, cmd=None, genVisit0=False):
        """Called from sps.smXLightSource or dcb.designId callbacks, this reset the current field and attempt to
        regenerate a new design file based on the current config."""
        cmd = self.bcast if cmd is None else cmd

        # fpsDesignId was not declared since pfi is connected, make sure to reset the current PfsField.
        if self.pfiConnected and self.getFpsDesignId() is None:
            self.visitManager.finishField()
            self.genPfsDesignKey(cmd)
            return

        designId, designed_at = self.mergeDesignFromCurrentSetup()

        # if pfi is connected, you do not want to declare a new field, unless you specifically asked for it.
        if self.pfiConnected and not genVisit0:
            return

        # declaring and loading a new PfsDesign, genVisit0 if a fps.convergence is expected.
        pfsDesign, visit0 = self.visitManager.declareNewField(designId, genVisit0=genVisit0)
        self.genPfsDesignKey(cmd)
        # Ingest design.
        designDB.ingest(cmd, pfsDesign, designed_at=designed_at)

    def mergeDesignFromCurrentSetup(self):
        """ Merge design given the current setup, there are basically two modes :
        When pfi is the only lightSource, in that case pfsDesignId is declared by users.
        When SuNSS &| DCB &| DCB2 are the light sources, since they are static, it can be generated automatically."""

        def genAutoDesign():
            """Generate a merged PfsDesign when SuNSS, DCB, DCB2 are connected to different spectrographs."""

            def pfsDesignDirName(lightSource):
                return os.path.join(self.actorConfig['pfsDesign']['rootDir'], lightSource)

            def getAflDesignId(lightSource, spectrographId):
                """Return correct designId for all fiber lamp."""
                if lightSource == 'afl9mtp':
                    return 0x0010000000000000
                elif lightSource == 'afl12mtp' and spectrographId in [1, 2]:
                    return 0x0100000000000000
                elif lightSource == 'afl12mtp' and spectrographId in [3, 4]:
                    return 0x1000000000000000

            gfm = pd.DataFrame(FiberIds().data)
            designToMerge = []
            designNames = []

            for specInd, lightSource in enumerate(self.buffer.lightSources):
                spectrographId = specInd + 1
                # adding engineering fibers.
                engDesign = PfsDesign.read(0xfacefeeb, pfsDesignDirName('engFibers'))
                designToMerge.append(engDesign[engDesign.spectrograph == spectrographId])

                if lightSource == 'none':
                    designNames.append('None')
                    continue  # just adding engineering fibers in that case.

                elif lightSource == 'sunss':
                    designNames.append('SuNSS')
                    pfsDesign = PfsDesign.read(0xdeadbeef, pfsDesignDirName(lightSource))
                    fiberHoleId = gfm[gfm.fiberId.isin(pfsDesign.fiberId)].fiberHoleId
                    allSpectro = gfm[gfm.fiberHoleId.isin(fiberHoleId)]
                    fiberId = allSpectro.query(f'spectrographId=={spectrographId}').fiberId.to_numpy().astype('int32')
                    pfsDesign.fiberId = fiberId
                    pfsDesign.objId = fiberId

                elif lightSource in {'dcb', 'dcb2', 'afl9mtp', 'afl12mtp'}:
                    if 'dcb' in lightSource:
                        designId = self.models[lightSource].keyVarDict['designId'].getValue()
                        designName = f'{lightSource}({self.models[lightSource].keyVarDict["fiberConfig"].getValue()})'
                        targetType = TargetType.DCB
                    else:
                        designId = getAflDesignId(lightSource, spectrographId)
                        designName = lightSource
                        targetType = TargetType.AFL

                    designNames.append(designName)
                    pfsDesign = PfsDesign.read(designId, pfsDesignDirName(lightSource))
                    pfsDesign = pfsDesign[pfsDesign.spectrograph == spectrographId]
                    pfsDesign.targetType = np.repeat(targetType, len(pfsDesign)).astype('int32')

                else:
                    raise ValueError(f'cannot merge design for {lightSource}')

                designToMerge.append(pfsDesign)

            return mergeDesign.mergeSuNSSAndDcb(designToMerge, designName=','.join(designNames))

        designed_at = None

        # no merging for pfi, at least for now.
        if self.pfiConnected:
            return self.getFpsDesignId(), designed_at

        # Proceed and generate the design automatically.
        mergedDesign = genAutoDesign()
        # Check if designFile already exists.
        if not os.path.isfile(os.path.join(self.actorConfig['pfsDesign']['rootDir'], mergedDesign.filename)):
            designed_at = 'now'
            mergedDesign.write(self.actorConfig['pfsDesign']['rootDir'])

        return mergedDesign.pfsDesignId, designed_at

    def getFpsDesignId(self):
        """Load persisted fpsDesignId."""
        try:
            designId, = self.actorData.loadKey('fpsDesignId')
        except:
            designId = None

        designId = int(designId, 16) if designId else designId
        return designId

    def setFpsDesignId(self, designId):
        """Persist fpsDesignId to disk."""
        designId = f'0x{designId:016x}' if designId else designId
        return self.actorData.persistKey('fpsDesignId', designId)

    def declareFpsDesign(self, cmd, designId=None, variant=0):
        """Declare current FpsDesignId, note that if only pfi is connected FpsDesignId==PfsDesignId."""
        cmdKeys = cmd.cmd.keywords
        designId = cmdKeys['designId'].values[0] if designId is None else designId
        variant = cmdKeys['variant'].values[0] if 'variant' in cmdKeys else variant

        # get actual pfsDesignId from designId0 and variant.
        if variant:
            designId = designDB.designIdFromVariant(designId0=designId, variant=variant)

        if not self.pfiConnected:
            raise RuntimeError('pfi is not connected, design will not declared as current.')

        # persist fps.pfsDesignId.
        self.setFpsDesignId(designId)
        # generate PfsDesign, specifically asking for to generate visit0.
        self.genPfsDesign(cmd, genVisit0=True)

    def fpsConfig(self, keyVar):
        """Callback called whenever fps.pfsConfig is generated."""
        try:
            designId, visit0, status = keyVar.getValue()
        except ValueError:
            return

        self.logger.info(f'fpsConfig={designId},{visit0},{status}')

        if status == 'Done' and self.visitManager.activeField:
            self.visitManager.activeField.loadPfsConfig0(designId, visit0)

    def updateFiberIllumination(self, keyVar):
        """Callback called whenever sps.fiberIllumination is generated."""
        try:
            visit, fiberIlluminationStatus = keyVar.getValue()
        except ValueError:
            return

        spsExpose = self.visitManager.activeVisit.get(visit, None)

        if not spsExpose:
            self.logger.warning(f'Could not find matching sps exposure with visit={visit}')
            return

        # update the illumination accordingly.
        spsExpose.updateFiberIllumination(fiberIlluminationStatus)

        # this is the last exposure of the sequence.
        lastExposure = len(spsExpose.sequence.remainingExposures) == 1

        # Finish command immediately.
        if spsExpose.sequence.returnWhenShutterClose and lastExposure:
            spsExpose.sequence.cmd.finish()
            spsExpose.sequence.cmd = None

    def genPfsDesignKey(self, cmd):
        """Generate pfsDesign keyword."""
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
        """Generate pfsConfig keyword."""
        cmd.inform('pfsConfig=0x%016x,%d,"%s",%.6f,%.6f,%.6f,"%s",0x%016x,%d,"%s"' % (pfsConfig.pfsDesignId,
                                                                                      pfsConfig.visit,
                                                                                      getDateDir(pfsConfig),
                                                                                      pfsConfig.raBoresight,
                                                                                      pfsConfig.decBoresight,
                                                                                      pfsConfig.posAng,
                                                                                      pfsConfig.designName,
                                                                                      pfsConfig.designId0,
                                                                                      pfsConfig.variant,
                                                                                      pfsConfig.decodeInstrumentStatusFlag()
                                                                                      ))


def main():
    theActor = IicActor('iic', productName='iicActor')
    theActor.run()


if __name__ == '__main__':
    main()
