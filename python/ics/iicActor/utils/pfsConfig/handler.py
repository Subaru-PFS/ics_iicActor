import logging

import ics.iicActor.utils.opdb as opdbUtils
import ics.utils.sps.fits as fits
import numpy as np
import pfs.utils.pfsConfigUtils as pfsConfigUtils
from pfs.datamodel.pfsConfig import FiberStatus, TargetType


class PfsConfigHandler:
    """
    A handler for managing and writing `pfsConfig` data associated with a given SPS exposure.
    """

    def __init__(self, spsExpose):
        """
        Initialize the PfsConfigHandler.

        Parameters
        ----------
        spsExpose : object
            The SPS exposure object containing visit information, exposure type,
            and sequence details.
        """
        self.spsExpose = spsExpose
        self.logger = logging.getLogger('pfsConfigHandler')

        # Retrieve additional pfsConfig metadata from FITS headers.
        cards = fits.getPfsConfigCards(spsExpose.iicActor, spsExpose.sequence.cmd, spsExpose.visitId,
                                       expType=spsExpose.exptype)

        # Create or retrieve the pfsConfig object for the current visit.
        pfsConfig = spsExpose.visitManager.activeField.getPfsConfig(spsExpose.visitId, cards=cards)

        # Ensure that pfsConfig arms match the arms used in the current sequence.
        pfsConfig.arms = spsExpose.sequence.matchPfsConfigArms(pfsConfig.arms)

        # Check if pfsConfig was simulated using pfsDesign (i.e., fake data).
        self.isFake = not np.nansum(np.abs(pfsConfig.pfiNominal - pfsConfig.pfiCenter))

        # Store the pfsConfig object for further operations.
        self.pfsConfig = pfsConfig

    @property
    def doUpdateEngineeringFiberStatus(self):
        return self.spsExpose.iicActor.actorConfig['pfsConfig']['doUpdateEngineeringFiberStatus']

    @property
    def doUpdateScienceFiberStatus(self):
        return self.spsExpose.iicActor.actorConfig['pfsConfig']['doUpdateScienceFiberStatus']

    def write(self):
        """
        Write the pfsConfig to disk and update relevant database entries.

        This method:
        - Saves the pfsConfig to disk.
        - Inserts the corresponding `pfs_config_sps` entry in the database.
        - Generates and logs a pfsConfig key for tracking purposes.
        """
        # Write the pfsConfig to the filesystem.
        pfsConfigUtils.writePfsConfig(self.pfsConfig)

        # Generate and log the pfsConfig key for tracking in the IIC actor.
        self.spsExpose.iicActor.genPfsConfigKey(self.spsExpose.sequence.cmd, self.pfsConfig)

    def insertInDB(self):
        """Insert an entry into the pfs_config_sps database table."""
        opdbUtils.insertPfsConfigSps(pfs_visit_id=self.pfsConfig.visit,
                                     visit0=self.spsExpose.visitManager.activeField.visit0)

    def updateFiberStatus(self, fiberIlluminationStatus):
        """
        Update the fiberStatus in the pfsConfig based on the fiberIlluminationStatus bitmask.

        Parameters
        ----------
        pfsConfigHandler : PfsConfigHandler
            Handler containing the pfsConfig to be updated.
        fiberIlluminationStatus : int
            8-bit integer where each pair of bits represents the illumination status
            of engineering and science fibers for one spectrograph module.
        """
        pfsConfig = self.pfsConfig

        for iSpec in range(4):
            specNum = iSpec + 1  # Spectrograph module number (1 to 4)

            # Extract the 2 bits for this spectrograph's status.
            status = (fiberIlluminationStatus >> (iSpec * 2)) & 0x3

            engIlluminated = status & 1  # Check if engineering fibers are illuminated.
            sciIlluminated = status & 2  # Check if science fibers are illuminated.

            # Select engineering fibers for this spectrograph.
            engFibers = ((pfsConfig.targetType == TargetType.ENGINEERING) &
                         (pfsConfig.spectrograph == specNum) &
                         (pfsConfig.fiberStatus == FiberStatus.GOOD))

            # Select science fibers for this spectrograph.
            scienceFibers = ((pfsConfig.targetType != TargetType.ENGINEERING) &
                             (pfsConfig.spectrograph == specNum) &
                             (pfsConfig.fiberStatus == FiberStatus.GOOD))

            # Update the fiber status based on the illumination state.
            if not engIlluminated and self.doUpdateEngineeringFiberStatus:
                pfsConfig.fiberStatus[engFibers] = FiberStatus.UNILLUMINATED
                self.logger.info(f'{pfsConfig.filename} SM{specNum} setting ENGINEERING fibers to UNILLUMINATED')

            if not sciIlluminated and self.doUpdateScienceFiberStatus:
                pfsConfig.fiberStatus[scienceFibers] = FiberStatus.UNILLUMINATED
                self.logger.info(f'{pfsConfig.filename} SM{specNum} setting SCIENCE fibers to UNILLUMINATED')
