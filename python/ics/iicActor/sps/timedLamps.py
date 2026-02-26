import ics.utils.sps.lamps.utils.lampState as lampState
from ics.iicActor.sps.expose import SpsExpose
from ics.iicActor.sps.sequence import SpsSequence


class TimedLampsSequence(SpsSequence):
    shutterRequired = False
    # Gross estimate and over-estimating
    ccdWipe = 10
    ccdRead = 50
    h4Read = 12
    h4Reset = h4Read * 2
    margin = 20

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

            wipeTime = self.h4Reset if 'n' in arms else self.ccdWipe
            readTime = self.h4Read if set(arms) == {'n'} else self.ccdRead

            estimatedTime = wipeTime + timedLamps[lamp]
            estimatedTime += (duplicate - 1) * (wipeTime + timedLamps[lamp] + readTime)

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
        if doImmediateGo:
            self.add(actor='lamps', cmdStr='stop')
