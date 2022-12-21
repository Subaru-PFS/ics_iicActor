#!/usr/bin/env python3

import actorcore.ICC
import numpy as np
import pfs.utils.pfsConfigUtils as pfsConfigUtils
from ics.utils.sps.spectroIds import getSite
from iicActor.utils import engine
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

            reactor.callLater(1, self.letsGetReadyToRumble)

    def letsGetReadyToRumble(self):
        """"""
        for actor in ['hub', 'sps']:
            self.cmdr.bgCall(callFunc=None, actor=actor, cmdStr='status')

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
