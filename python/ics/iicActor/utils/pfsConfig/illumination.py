import logging

from pfs.datamodel.pfsConfig import FiberStatus, TargetType


def updateFiberStatus(pfsConfig, fiberIlluminationStatus,
                      doUpdateEngineeringFiberStatus=True, doUpdateScienceFiberStatus=True):
    """
    Updates the fiber status within `pfsConfig` based on an 8-bit fiber illumination status bitmask.

    This function examines the 8-bit integer `fiberIlluminationStatus`, where each pair of bits
    represents the illumination state for engineering and science fibers in each spectrograph module (SM1 to SM4).
    The function uses this information to update the `fiberStatus` attribute in `pfsConfig`:
    - Sets the status to `UNILLUMINATED` for fibers that are not illuminated, if specified.

    Parameters
    ----------
    pfsConfig : PfsConfig
        The configuration object containing fiber information, including `fiberStatus`, `targetType`, and `spectrograph`.
    fiberIlluminationStatus : int
        An 8-bit integer bitmask where each spectrograph module (SM1 to SM4) has 2 bits representing the illumination
        status of engineering and science fibers. The two bits encode:
        - 0: Both fibers are unilluminated.
        - 1: Only engineering fibers are illuminated.
        - 2: Only science fibers are illuminated.
        - 3: Both fibers are illuminated.
    doUpdateEngineeringFiberStatus : bool, optional
        If True, updates the status of engineering fibers based on illumination state (default is True).
    doUpdateScienceFiberStatus : bool, optional
        If True, updates the status of science fibers based on illumination state (default is True).

    Notes
    -----
    - Only fibers with `FiberStatus.GOOD` in `pfsConfig` are updated.
    - A log entry is created for each update applied to a spectrograph module.
    """

    logger = logging.getLogger('spsExpose')

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
        if not engIlluminated and doUpdateEngineeringFiberStatus:
            pfsConfig.fiberStatus[engFibers] = FiberStatus.UNILLUMINATED
            logger.info(f'{pfsConfig.filename} SM{specNum} setting ENGINEERING fibers to UNILLUMINATED')

        if not sciIlluminated and doUpdateScienceFiberStatus:
            pfsConfig.fiberStatus[scienceFibers] = FiberStatus.UNILLUMINATED
            logger.info(f'{pfsConfig.filename} SM{specNum} setting SCIENCE fibers to UNILLUMINATED')
