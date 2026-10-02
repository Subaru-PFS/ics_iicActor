import math

import ics.iicActor.utils.translate as translate
import ics.utils.sps.lamps.utils.lampState as lampState
from ics.iicActor.sps.expose import SpsExpose
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.sps.subcmd import ReleaseIlluminator
from ics.utils.sps.exposureTiming import ExposureTiming


class TimedLampsSequence(SpsSequence):
    shutterRequired = False

    @staticmethod
    def computeLampTotalSecs(lampTime, arms, duplicate, h4ReadSecs, h4IrpRatio, roundToSecs=5):
        """Return how long a lamp lit for a sequence of duplicated exposures must burn, in seconds.

        That is until the last shutter close, from the exposure timing model shared with sps,
        rounded up to the next multiple of `roundToSecs`.
        """
        exposureTiming = ExposureTiming.fromInstdata()
        totalSecs = exposureTiming.lampOnTime(lampTime, arms, readTime=h4ReadSecs, irpRatio=h4IrpRatio,
                                              duplicate=duplicate)
        return int(roundToSecs * math.ceil(totalSecs / roundToSecs))

    def expose(self, exptype, lampKeys, cams, duplicate=1, windowKeys=None, slideSlit=None):
        """Override expose function to handle dcb/pfilamps lampKeys arguments."""

        def prepareTotalLampTime(timedLamps, candidates=('hgcd', 'hgar')):
            [lamp] = [lamp for lamp in candidates if lamp in timedLamps]
            arms = set([cam.arm for cam in cams])
            estimatedTime = TimedLampsSequence.computeLampTotalSecs(timedLamps[lamp], arms=arms, duplicate=duplicate,
                                                                     h4ReadSecs=h4ReadTime, h4IrpRatio=h4IrpRatio)
            return estimatedTime, f'prepare {lamp}={estimatedTime}'

        windowKeys = dict() if windowKeys is None else windowKeys
        lampKeys = lampKeys.copy()
        h4ReadTime = lampKeys.pop('h4ReadTime', None)
        h4IrpRatio = lampKeys.pop('h4IrpRatio', None)

        # retrieving iis keys.
        iisKeys = lampKeys.pop('iis', dict())
        shutterTiming = lampKeys.get('shutterTiming', 0)

        doIIS, maxIisLampOnTime, IisCmdStr = translate.timedLampsCmdStr(iisKeys)
        doLamps, maxLampOnTime, lampsCmdStr = translate.timedLampsCmdStr(lampKeys)

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
        # illuminators lit here rather than by each exposure, sps needs to be told to stop them.
        bckIlluminators = []

        if doImmediateGo:
            estimatedTime, lampsCmdStr = prepareTotalLampTime(lampKeys)
            self.add(actor='lamps', cmdStr=lampsCmdStr)
            self.add(actor='lamps', cmdStr='waitForReadySignal', timeLim=240)
            self.add(actor='lamps', cmdStr='go noWait')
            # enforce doShutterTiming and doLamps to False.
            doShutterTiming = False
            doLamps = False
            bckIlluminators.append(self.lightSource.lampsActor)

        if doIisImmediateGo:
            estimatedIisTime, IisCmdStr = prepareTotalLampTime(iisKeys, candidates=('hgar',))
            self.add(actor='iis', cmdStr=IisCmdStr)
            self.add(actor='iis', cmdStr='waitForReadySignal', timeLim=240)
            self.add(actor='iis', cmdStr='go noWait')
            # iis hgar is now running for the whole sequence; per-exposure iis pulse no longer needed.
            doShutterTiming = False
            doIIS = False
            bckIlluminators.append('iis')

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
                                          bckIlluminators=bckIlluminators if bckIlluminators else None,
                                          isLast=nExposure == duplicate - 1,
                                          **windowKeys)
            list.append(self, spsExpose)

        # sps releases those at the close of the last exposure; whatever else ends the run, the tail does.
        for actor in bckIlluminators:
            self.tail.append(ReleaseIlluminator(self, actor, lastExposure=spsExpose))

