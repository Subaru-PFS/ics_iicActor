import logging

import ics.iicActor.utils.lib as libUtils
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.utils import exception
from ics.iicActor.utils.resources import resource
from ics.utils.sps.config import SpsConfig


class ResourceManager(object):
    """Manage software/hardware resource availability and locking for actor commands."""

    ignore = ['hub', 'keys', 'msg', 'iic', 'gen2', 'sequencepanel']

    def __init__(self, actor):
        """Initialize the resource manager and attach callbacks."""
        self.actor = actor
        self.logger = logging.getLogger('resourceManager')
        self.connectedActors = dict()
        self.spsResources = dict()
        self.spsConfig = None
        self.attachCallbacks()

    @property
    def resources(self):
        """Return a combined dict of connected actor and SPS resources."""
        return dict([it for it in self.connectedActors.items()] + [it for it in self.spsResources.items()])

    def attachCallbacks(self):
        """Attach hub/sps model callbacks to track resource availability."""

        def connectedActors(keyVar):
            """Track current list of connected actors."""
            actorList = list(map(str, keyVar.getValue()))

            for actorName in actorList:
                if actorName in self.connectedActors or actorName in ResourceManager.ignore:
                    continue

                self.connectedActors[actorName] = resource.Resource.getActor(actorName)

            # Remove disconnected actors
            disconnected = set(self.connectedActors) - set(actorList)

            for actorName in disconnected:
                self.connectedActors.pop(actorName, None)

        def spsConfig(keyVar):
            """Track changes to spsModules and reload related resources."""
            self.spsConfig = self.reloadSpsResources()

        self.actor.models['hub'].keyVarDict['actors'].addCallback(connectedActors)
        self.actor.models['sps'].keyVarDict['spsModules'].addCallback(spsConfig)

    def reloadSpsResources(self):
        """Rebuild spsConfig and sps resource pool."""
        try:
            spsConfig = SpsConfig.fromModel(self.actor.models['sps'])
        except ValueError:
            return None

        parts = list(map(str, sum([specModule.opeSubSys for specModule in spsConfig.values()], [])))

        for partName in parts:
            # just ignore in that case.
            if partName in self.spsResources:
                continue

            self.spsResources[partName] = resource.Resource.getPart(partName)

        # Remove any parts no longer available
        disconnected = set(self.spsResources) - set(parts)
        for partName in disconnected:
            self.spsResources.pop(partName, None)

        return spsConfig

    def request(self, resources):
        """Try to lock a list of resource names, raise if unavailable."""
        notConnected = []
        isBusy = []
        locked = []

        for required in resources:
            required, state = resource.Resource.translate(required)

            # checking for unconnected resources.
            if required not in self.resources:
                notConnected.append(required)
                continue
            # checking for unavailable resources.
            if not self.resources[required].isAvailable(state):
                isBusy.append(required)

        if notConnected:
            raise exception.ResourceUnAvailable(f'{",".join(notConnected)} not connected.')

        if isBusy:
            raise exception.ResourceIsBusy(f'{",".join(isBusy)} already busy.')

        # all tests have passed we can lock everything down
        self.logger.info(f'locking resources : {",".join(resources)}')

        for required in resources:
            required, state = resource.Resource.translate(required)
            self.resources[required].lock(state)
            # keeping only the locked resources.
            locked.append(required)

        return locked

    def free(self, locked):
        """Free a list of locked resource names."""
        locked = [key for key in locked if key in self.resources and not self.resources[key].available]

        # if nothing to be freed just return.
        if not locked:
            return

        self.logger.info(f'freeing resources : {",".join(locked)}')
        for resource in locked:
            self.resources[resource].free()

    def inspect(self, sequence):
        """Extract required resources from a given command sequence."""
        # just get the list of all actors that will be called as start.
        allDeps = list(set([subCmd.actor for subCmd in sequence.subCmds]))

        # MCS implicitly needed for some FPS commands
        if 'fps' in allDeps:
            for fpsCommand in list(set([subCmd.cmdHead for subCmd in sequence.subCmds if subCmd.actor == 'fps'])):
                # This command requires fps only, might be the only one, actually.
                if fpsCommand in ['cobraMoveSteps', 'calculateBoresight']:
                    continue

                allDeps.append('mcs')

        # sps is somehow peculiar because it's not driving hardware directly just actors (enu, xcu, ccd...).
        if 'sps' in allDeps:
            allDeps.remove('sps')
            if isinstance(sequence, SpsSequence):
                if sequence.noDeps:  # just cams
                    deps = list(map(str, sequence.cams))
                else:
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

    def freeEnu(self, keyVar):
        """Free RDA, and FCA resources for the specified spectrograph."""
        specNum = int(keyVar.actor[-1])
        try:
            shutterState = self.actor.models[keyVar.actor].keyVarDict['shutters'].getValue()
        except ValueError:
            return

        if shutterState == 'close':
            # freeing fca and rda, as we decided that bia should be still off while reading.
            keys = [f'{resource}_sm{specNum}' for resource in ['fca', 'rda']]
            # making sure that the resource exist.
            resources = list(set(keys).intersection(self.resources.keys()))
            self.free(resources)
