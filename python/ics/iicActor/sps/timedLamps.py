import ics.utils.sps.lamps.utils.lampState as lampState
from ics.iicActor.sps.expose import SpsExpose
from ics.iicActor.sps.sequence import SpsSequence


class TimedLampsSequence(SpsSequence):
    shutterRequired = False

    # Gross estimate and over-estimating

    @staticmethod
    def computeLampTotalSecs(lampTime, arms, duplicate, marginSecs=5, roundToSecs=5):
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
        h4ReadSecs = 10.8

        hasNir = 'n' in arms
        hasOnlyNir = set(arms) == {'n'}

        h4ReadCount = computeH4ReadCount(lampTime, h4ReadSecs=h4ReadSecs)
        resetSecs = 2 * h4ReadSecs if hasNir else 0

        ccdTotalSecs = 0 if hasOnlyNir else lampTime + ccdWipeSecs + ccdReadSecs
        nirTotalSecs = h4ReadCount * h4ReadSecs if hasNir else 0

        shutterOpenAfterSecs = resetSecs + max(ccdWipeSecs, h4ReadSecs)
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

        def prepareTotalLampTime(timedLamps):
            [lamp] = [lamp for lamp in ['hgcd', 'hgar'] if lamp in timedLamps]
            arms = set([cam.arm for cam in cams])
            estimatedTime = TimedLampsSequence.computeLampTotalSecs(timedLamps[lamp], arms=arms, duplicate=duplicate)
            return estimatedTime, f'prepare {lamp}={estimatedTime}'

        windowKeys = dict() if windowKeys is None else windowKeys
        lampKeys = lampKeys.copy()

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

        if doImmediateGo:
            estimatedTime, lampsCmdStr = prepareTotalLampTime(lampKeys)
            self.add(actor='lamps', cmdStr=lampsCmdStr)
            self.add(actor='lamps', cmdStr='waitForReadySignal', timeLim=240)
            self.add(actor='lamps', cmdStr='go noWait')
            # enforce doShutterTiming and doLamps to False.
            doShutterTiming = False
            doLamps = False

        for nExposure in range(duplicate):
            # adding iis and lamps prepare commands.
            if doIIS:
                self.add(actor='sps', cmdStr=f'iis {IisCmdStr}', cams=cams)
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
