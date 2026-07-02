import ics.utils.sps.lamps.utils.lampState as lampState
from ics.iicActor.sps.expose import SpsExpose
from ics.iicActor.sps.sequence import SpsSequence


class TimedLampsSequence(SpsSequence):
    shutterRequired = False

    # Gross estimate and over-estimating

    @staticmethod
    def computeLampTotalSecs(lampTime, arms, duplicate, h4ReadSecs, marginSecs=5, roundToSecs=5):
        """Return the total lamp time in seconds for a sequence of duplicated exposures.

        Assumptions:
        - If 'n' is in `arms`, the NIR (H4RG) detector uses ramp reads of length `h4ReadSecs`.
        - If any non-NIR arm is present, a CCD exposure includes wipe + read overhead.
        - Shutter opens after the reset + max(wipe, h4 read) and stays open for `lampTime`.

        Timing model:
        - A per-exposure safety margin (`marginSecs`) is added:
            * to each full exposure cycle
            * to the final shutter-close time
        - For `duplicate > 1`, all but the last exposure use the full detector cycle duration.
        - The last exposure ends at shutter close (not at the end of a full detector cycle).

        Rounding:
        - The final total is rounded *up* to the next multiple of `roundToSecs`.
        """

        def computeH4ReadCount(lampTime, h4ReadSecs):
            """Compute number of H4RG reads (including minimum + extra reads)."""
            rampConfig = dict(nReadMin=3, nExtraRead=1)  # Extra-read added to safely synchronize H4.
            overheadSecs = 0  # Overhead included in read-count calculation, if any.
            nReadMin = rampConfig['nReadMin'] + rampConfig['nExtraRead']
            return int(round((lampTime + overheadSecs) // h4ReadSecs + nReadMin))

        ccdWipeSecs = 10.0
        ccdReadSecs = 45.0

        hasNir = 'n' in arms
        hasOnlyNir = set(arms) == {'n'}

        h4ReadCount = computeH4ReadCount(lampTime, h4ReadSecs=h4ReadSecs) if hasNir else 0
        resetSecs = 2 * h4ReadSecs if hasNir else 0

        ccdTotalSecs = 0 if hasOnlyNir else lampTime + ccdWipeSecs + ccdReadSecs
        nirTotalSecs = h4ReadCount * h4ReadSecs if hasNir else 0

        openDelays = ([ccdWipeSecs] if not hasOnlyNir else []) + ([h4ReadSecs] if hasNir else [])
        shutterOpenAfterSecs = resetSecs + max(openDelays)
        shutterCloseAfterSecs = shutterOpenAfterSecs + lampTime + marginSecs
        exposureTotalSecs = resetSecs + max(ccdTotalSecs, nirTotalSecs) + marginSecs

        totalSecs = (duplicate - 1) * exposureTotalSecs + shutterCloseAfterSecs
        roundedSecs = int(roundToSecs * (totalSecs // roundToSecs))

        return roundedSecs

    def expose(self, exptype, lampKeys, cams, duplicate=1, windowKeys=None, slideSlit=None):
        """Override expose function to handle dcb/pfilamps lampKeys arguments."""

        def doTimedLamps(timedLamps):
            exptime = 0.0
            lamps = []

            for lamp in lampState.allLamps:
                # ignore lampTime set to 0.0
                if lamp in timedLamps.keys() and timedLamps[lamp]:
                    exptime = max(exptime, timedLamps[lamp])
                    lamps.append(f"{lamp}={timedLamps[lamp]}")

            return len(lamps) != 0, exptime, f'prepare {" ".join(lamps)}'

        def prepareTotalLampTime(timedLamps, candidates=('hgcd', 'hgar')):
            [lamp] = [lamp for lamp in candidates if lamp in timedLamps]
            arms = set([cam.arm for cam in cams])
            estimatedTime = TimedLampsSequence.computeLampTotalSecs(timedLamps[lamp], arms=arms, duplicate=duplicate,
                                                                     h4ReadSecs=h4ReadTime)
            return estimatedTime, f'prepare {lamp}={estimatedTime}'

        windowKeys = dict() if windowKeys is None else windowKeys
        lampKeys = lampKeys.copy()
        h4ReadTime = lampKeys.pop('h4ReadTime', None)

        # retrieving iis keys.
        iisKeys = lampKeys.pop('iis', dict())
        shutterTiming = lampKeys.get('shutterTiming', 0)

        doIIS, maxIisLampOnTime, IisCmdStr = doTimedLamps(iisKeys)
        doLamps, maxLampOnTime, lampsCmdStr = doTimedLamps(lampKeys)

        # setting shutter exptime accordingly.
        doShutterTiming = shutterTiming > 0
        exptime = shutterTiming if doShutterTiming else max(maxLampOnTime, maxIisLampOnTime)

        # small note here, the longer wait will happen in the expose command, not prepare.
        # pfilamps.waitForReadySignal() is where its happening, ~2s for qth, immediate for neon,krypton,argon,xenon.
        # for hgcd can take up to 2 minutes ! It won't work on n arm with the current scheme, but I think most hgcd
        # lines are in the blue anyway.

        # other scheme when lamp is turn on before end. INSTRM-2184.
        doImmediateGo = 'hgcd' in lampsCmdStr or 'hgar' in lampsCmdStr
        doIisImmediateGo = 'hgar' in IisCmdStr

        if doImmediateGo:
            estimatedTime, lampsCmdStr = prepareTotalLampTime(lampKeys)
            self.add(actor='lamps', cmdStr=lampsCmdStr)
            self.add(actor='lamps', cmdStr='waitForReadySignal', timeLim=240)
            self.add(actor='lamps', cmdStr='go noWait')
            # enforce doShutterTiming and doLamps to False.
            doShutterTiming = False
            doLamps = False

        if doIisImmediateGo:
            estimatedIisTime, IisCmdStr = prepareTotalLampTime(iisKeys, candidates=('hgar',))
            self.add(actor='iis', cmdStr=IisCmdStr)
            self.add(actor='iis', cmdStr='waitForReadySignal', timeLim=240)
            self.add(actor='iis', cmdStr='go noWait')
            # iis hgar is now running for the whole sequence; per-exposure iis pulse no longer needed.
            doShutterTiming = False
            doIIS = False

        for nExposure in range(duplicate):
            # adding iis and lamps prepare commands.
            if doIIS:
                self.add(actor='iis', cmdStr=IisCmdStr)
            if doLamps:
                self.add(actor='lamps', cmdStr=lampsCmdStr)

            # creating SpsExpose command object.
            spsExpose = SpsExpose.specify(self, exptype, exptime, cams,
                                          doLamps=doLamps, doIIS=doIIS,
                                          doShutterTiming=doShutterTiming,
                                          doTest=self.doTest,
                                          doScienceCheck=self.doScienceCheck, skipBiaCheck=self.skipBiaCheck,
                                          slideSlit=slideSlit,
                                          **windowKeys)
            list.append(self, spsExpose)

        # stop lamp in the end because we're done
        # if doImmediateGo:
        #    self.add(actor='lamps', cmdStr='stop')
