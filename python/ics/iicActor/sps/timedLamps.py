import ics.utils.sps.lamps.utils.lampState as lampState
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.subcmd import SpsExpose


class TimedLampsSequence(SpsSequence):
    shutterRequired = False

    def expose(self, exptype, lampKeys, cams, duplicate=1, windowKeys=None, slideSlit=None):
        """Override expose function to handle dcb/pfilamps lampKeys arguments."""
        windowKeys = dict() if windowKeys is None else windowKeys

        def doTimedLamps(timedLamps):
            exptime = 0.0
            lamps = []

            for lamp in lampState.allLamps:
                # ignore lampTime set to 0.0
                if lamp in timedLamps.keys() and timedLamps[lamp]:
                    exptime = max(exptime, timedLamps[lamp])
                    lamps.append(f"{lamp}={timedLamps[lamp]}")

            return len(lamps) != 0, exptime, f'prepare {" ".join(lamps)}'

        # retrieving iis keys.
        iisKeys = lampKeys.pop('iis', None)

        doIIS, maxIisLampOnTime, IisCmdStr = doTimedLamps(iisKeys)
        doLamps, maxLampOnTime, lampsCmdStr = doTimedLamps(lampKeys)

        # small note here, the longer wait will happen in the expose command, not prepare.
        # pfilamps.waitForReadySignal() is where its happening, ~2s for qth, immediate for neon,krypton,argon,xenon.
        # for hgcd can take up to 2 minutes ! It won't work on n arm with the current scheme, but I think most hgcd
        # lines are in the blue anyway.
        timeOffset = 240 if ('hgcd' in lampsCmdStr or 'hgar' in lampsCmdStr) else 90

        if lampKeys['shutterTiming']:
            exptime = lampKeys['shutterTiming']
            doShutterTiming = True
        else:
            exptime = max(maxLampOnTime, maxIisLampOnTime)
            doShutterTiming = False

        for nExposure in range(duplicate):
            # adding iis and lamps prepare commands.
            if doIIS:
                self.add(actor='sps', cmdStr=f'iis {IisCmdStr}', cams=cams)
            if doLamps:
                self.add(actor='lamps', cmdStr=lampsCmdStr)

            # creating SpsExpose command object.
            spsExpose = SpsExpose.specify(self, exptype, exptime, cams,
                                          doLamps=doLamps, doIIS=doIIS,
                                          doShutterTiming=doShutterTiming, timeOffset=timeOffset,
                                          doTest=self.doTest, doScienceCheck=self.doScienceCheck, slideSlit=slideSlit,
                                          **windowKeys)
            list.append(self, spsExpose)
