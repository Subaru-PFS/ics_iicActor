#!/usr/bin/env python3

import os

import actorcore.ICC
import iicActor.utils.mergePfsDesign as merge
import numpy as np
import pandas as pd
import pfs.utils.pfsConfigUtils as pfsConfigUtils
from ics.utils.sps.spectroIds import getSite
from iicActor.utils import engine
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
        self.engine = engine.Engine(self)

        self.buffer = dict()
        self.buffer['lightSources'] = self.loadLightSources()
        self.buffer['dcbDesignId'] = self.loadDcbDesignId('dcb')
        self.buffer['dcb2DesignId'] = self.loadDcbDesignId('dcb2')

        self.everConnected = False

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
                self.models['sps'].keyVarDict[f'sm{spectrographId}LightSource'].addCallback(self.hasLightSourceChanged)

            for dcb in {'dcb', 'dcb2'}:
                self.models[dcb].keyVarDict['designId'].addCallback(self.hasDcbConfigChanged)

            reactor.callLater(1, self.letsGetReadyToRumble)

    def letsGetReadyToRumble(self):
        """"""
        for actor in ['hub', 'sps']:
            self.cmdr.bgCall(callFunc=None, actor=actor, cmdStr='status')

    def loadLightSources(self):
        """"""
        lightSources = []

        spsKeys = self.actorData.loadKeys('sps')
        for spectrographId in range(1, 5):
            try:
                lightSource, = spsKeys[f'sm{spectrographId}LightSource']
            except:
                lightSource = None

            lightSources.append(lightSource)

        return lightSources

    def loadDcbDesignId(self, dcbName):
        """"""
        try:
            designId, = self.actorData.loadKeys(dcbName)['pfsDesignId']
        except:
            designId = '0x0'

        return int(designId, 16)

    def hasLightSourceChanged(self, keyVar):
        """"""
        lightSources = self.loadLightSources()
        if lightSources != self.buffer['lightSources']:
            # clearing pfsField
            self.buffer['lightSources'] = lightSources
            self.updatePfsField()

    def hasDcbConfigChanged(self, keyVar):
        """"""
        dcbName = keyVar.actor
        designId = self.loadDcbDesignId(dcbName)

        if designId != self.buffer[f'{dcbName}DesignId']:
            self.buffer[f'{dcbName}DesignId'] = designId
            if dcbName in self.buffer['lightSources']:
                self.updatePfsField()

    def updatePfsField(self):
        # clearing pfsField
        self.engine.visitManager.finishField()
        self.genPfsDesignKey(self.bcast)

        def genAutoDesign():
            """"""
            gfm = pd.DataFrame(FiberIds().data)
            designToMerge = []

            for specInd, lightSource in enumerate(self.buffer['lightSources']):
                if lightSource is None:
                    continue

                spectrographId = specInd + 1
                designId = 0xdeadbeef if lightSource == 'sunss' else self.models[lightSource].keyVarDict['designId'].getValue()
                dirName = os.path.join(self.actorConfig['pfsDesign']['rootDir'], lightSource)
                pfsDesign = PfsDesign.read(designId, dirName)

                if lightSource == 'sunss':
                    fiberId = gfm[gfm.fiberHoleId.isin(pfsDesign.fiberId)].query(f'spectrographId=={spectrographId}').fiberId.to_numpy().astype('int32')
                    pfsDesign.fiberId = fiberId
                    pfsDesign.objId = fiberId

                elif lightSource in {'dcb', 'dcb2'}:
                    pfsDesign = pfsDesign[pfsDesign.spectrograph == spectrographId]
                    pfsDesign.targetType = np.repeat(TargetType.DCB, len(pfsDesign)).astype('int32')

                else:
                    raise ValueError(f'cannot merge design for {lightSource}')

                designToMerge.append(pfsDesign)

            return merge.mergeSunssAndDcbDesign(designToMerge)

        if 'pfi' not in self.buffer['lightSources']:
            design = genAutoDesign()
            # check if designFile already exists.
            if not os.path.isfile(os.path.join(self.actorConfig['pfsDesign']['rootDir'], design.filename)):
                design.write(self.actorConfig['pfsDesign']['rootDir'])

            # no visit0 concept in that case.
            self.engine.visitManager.declareNewField(design.pfsDesignId, genVisit0=False)
            self.genPfsDesignKey(self.bcast)

    def genPfsDesignKey(self, cmd):
        """"""
        activeField = self.engine.visitManager.activeField
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

    def genPfsConfig0Key(self, cmd):
        """"""
        activeField = self.engine.visitManager.activeField
        pfsConfig0 = None if activeField is None else activeField.pfsConfig0

        designId = 0 if pfsConfig0 is None else pfsConfig0.pfsDesignId
        visit0 = 0 if pfsConfig0 is None else pfsConfig0.visit
        dateDir = 'None' if pfsConfig0 is None else pfsConfigUtils.getDateDir(pfsConfig0)
        raBoresight = np.NaN if pfsConfig0 is None else pfsConfig0.raBoresight
        decBoresight = np.NaN if pfsConfig0 is None else pfsConfig0.decBoresight
        posAng = np.NaN if pfsConfig0 is None else pfsConfig0.posAng
        designName = 'None' if pfsConfig0 is None else pfsConfig0.designName
        designId0 = 0 if pfsConfig0 is None else pfsConfig0.designId0
        variant = 0 if pfsConfig0 is None else pfsConfig0.variant

        cmd.inform('pfsConfig0=0x%016x,%d,"%s",%.6f,%.6f,%.6f,"%s",0x%016x,%d' % (designId,
                                                                                  visit0,
                                                                                  dateDir,
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
