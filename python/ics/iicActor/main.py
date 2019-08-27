#!/usr/bin/env python3

import actorcore.ICC

class IicActor(actorcore.ICC.ICC):
    def __init__(self, name,
                 productName=None,
                 debugLevel=30):

        """ Setup an Actor instance. See help for actorcore.Actor for details. """

        # This sets up the connections to/from the hub, the logger, and the twisted reactor.
        #
        actorcore.ICC.ICC.__init__(self, name, 
                                   productName=productName)

        # No quite sure what to do about this yet. But one of the
        # "clocks" of the PFS is the single visit, for which the IIC
        # is responsible for distributing to sub actors.
        #
        self.activeVisit = None

        self.everConnected = False

    def connectionMade(self):
        if self.everConnected is False:
            self.logger.info("Establishing first tron connection...")
            self.everConnected = True

            _needModels = [self.name, "gen2",
                           "fps", "mcs"]
            self.logger.info(f'adding models: {_needModels}')
            self.addModels(_needModels)
            self.logger.info(f'added models: {self.models.keys()}')

#
# To work
def main():
    theActor = IicActor('iic', productName='iicActor')
    theActor.run()

if __name__ == '__main__':
    main()
