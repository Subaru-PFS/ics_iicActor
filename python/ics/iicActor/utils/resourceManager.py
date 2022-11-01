import logging

import iicActor.utils.lib as libUtils
from ics.iicActor.sps.sequence import SpsSequence
from ics.utils.sps.config import SpsConfig
from iicActor.utils import exception


class Resource(object):
    def __init__(self, name):
        self.name = name
        self.available = True

    def lock(self):
        """"""
        if not self.available:
            raise exception.ResourceIsBusy(f'{self.name} already busy.')

        self.available = False

    def free(self):
        """"""
        self.available = True


class ResourceManager(object):
    ignore = ['hub', 'keys', 'msg', 'iic', 'gen2', 'sequencepanel']

    """ Placeholder to reject/accept incoming jobs based on the availability of the software/hardware. """

    def __init__(self, actor):
        self.actor = actor
        self.logger = logging.getLogger('resourceManager')
        self.connectedActors = dict()
        self.spsResources = dict()

        self.spsConfig = None
        self.attachCallbacks()

    @property
    def resources(self):
        return dict([it for it in self.connectedActors.items()] + [it for it in self.spsResources.items()])

    def attachCallbacks(self):
        """Attaching callbacks for hub.actors and sps.spsModules"""

        def connectedActors(keyVar):
            """Always keep an up-to-date inventory of the connected actors."""
            actorList = list(map(str, keyVar.getValue()))

            for actorName in actorList:
                if actorName in self.connectedActors or actorName in ResourceManager.ignore:
                    continue

                self.connectedActors[actorName] = Resource(actorName)

            # also check for actors that disappeared.
            disconnected = set(self.connectedActors) - set(actorList)

            for actorName in disconnected:
                self.connectedActors.pop(actorName, None)

        def spsConfig(keyVar):
            """Always keep an up-to-date inventory of the spsConfig and resources."""
            self.spsConfig = self.reloadSpsResources()

        self.actor.models['hub'].keyVarDict['actors'].addCallback(connectedActors)
        self.actor.models['sps'].keyVarDict['spsModules'].addCallback(spsConfig)

    def reloadSpsResources(self):
        """Reloading spsConfig and resources."""
        # getting all the current operational parts.
        try:
            spsConfig = SpsConfig.fromModel(self.actor.models['sps'])
        except ValueError:
            return None

        parts = list(map(str, sum([specModule.opeSubSys for specModule in spsConfig.values()], [])))

        for partName in parts:
            if partName in self.spsResources:
                continue

            self.spsResources[partName] = Resource(partName)

        # also check for parts that are no longer available.
        disconnected = set(self.spsResources) - set(parts)
        for partName in disconnected:
            self.spsResources.pop(partName, None)

        return spsConfig

    def request(self, resources):
        """Requesting and locking given resources."""
        notConnected = []
        isBusy = []

        for required in resources:
            # checking for unconnected resources.
            if required not in self.resources:
                notConnected.append(required)
                continue
            # checking for unavailable resources.
            if not self.resources[required].available:
                isBusy.append(required)

        if notConnected:
            raise exception.ResourceUnAvailable(f'{",".join(notConnected)} not connected.')

        if isBusy:
            raise exception.ResourceIsBusy(f'{",".join(isBusy)} already busy.')

        # all tests have passed we can lock everything down
        self.logger.info(f'locking resources : {",".join(resources)}')
        for required in resources:
            self.resources[required].lock()

        return resources

    def free(self, locked):
        """Freeing resources."""
        # is nothing got locked just return.
        if locked is None:
            return

        self.logger.info(f'freeing resources : {",".join(locked)}')
        for resource in locked:
            if resource not in self.resources:
                continue

            self.resources[resource].free()

    def inspect(self, sequence):
        """Inspect sequence object and find-out what resources needs to be booked."""
        # just get the list of all actors that will be called as start.
        allDeps = list(set([subCmd.actor for subCmd in sequence.subCmds]))

        # most fps command use mcs as well.
        if 'fps' in allDeps:
            for fpsCommand in list(set([subCmd.cmdHead for subCmd in sequence.subCmds if subCmd.actor == 'fps'])):
                # This command requires fps only, might be the only one, actually.
                if fpsCommand in ['cobraMoveSteps', 'calculateBoresight']:
                    continue

                allDeps.append('mcs')

        # sps is somehow peculiar because it's not driving hardware directly just actors (enu, xcu, hx, ccd, ...).
        if 'sps' in allDeps:
            allDeps.remove('sps')
            if isinstance(sequence, SpsSequence):
                # dependencies are derived from cams.
                deps = list(set(map(str, sum([cam.dependencies(sequence) for cam in sequence.cams], []))))
                allDeps.extend(deps)
            else:
                for spsCommand in list(set([subCmd for subCmd in sequence.subCmds if subCmd.actor == 'sps'])):
                    # selecting spectrograph modules from the command inputs.
                    specNums = libUtils.identSpecNums(spsCommand.cmdStr)
                    specModules = self.spsConfig.selectModules(specNums)
                    # select resource based on cmdHead.
                    if spsCommand.cmdHead == 'bia':
                        allDeps.extend([str(specModule.bia) for specModule in specModules])
                    elif spsCommand.cmdHead == 'rda':
                        allDeps.extend([str(specModule.rda) for specModule in specModules])
                    elif spsCommand.cmdHead == 'slit':
                        allDeps.extend([str(specModule.fca) for specModule in specModules])
                    else:
                        raise RuntimeError(f'dont know what to do with {spsCommand.cmdHead}...')

        return list(set(allDeps))
