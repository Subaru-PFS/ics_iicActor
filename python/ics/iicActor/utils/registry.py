from ics.iicActor.sequenceList.fps import FpsSequence
from ics.iicActor.sps.sequence import SpsSequence
from ics.iicActor.utils.sequence import Sequence
from iicActor.utils import exception


class Registry(dict):
    """Placeholder to record and interact with sequence"""

    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def register(self, sequence):
        """Registering sequence"""
        # adding the new sequence.
        self[sequence.sequence_id] = sequence
        # cleaning up the whole registry.
        self.cleaningUp()

    def cleaningUp(self):
        """Cleaning up obsolete sequences."""
        # obsolete inventory
        obsoletes = [sequence.sequence_id for sequence in self.values() if sequence.isObsolete]

        for sequenceId in obsoletes:
            self.pop(sequenceId, None)

    def getActives(self, filter=''):
        """Return sequence_id for actives sequences."""
        # define sequence class.
        actives = [seq.sequence_id for seq in self.values() if seq.match(filter) and seq.status.isActive]
        # no need to go further.
        if not actives:
            raise exception.SequenceIdentificationFailure(f'no sequence is currently active.')

        return actives

    def identify(self, cmdKeys, filter=''):
        """Return the active sequence based on cmdKeys."""
        # get active sequence_ids

        actives = self.getActives(filter=filter)
        # get sequence_id provided by the user.
        selected_id = int(cmdKeys['id'].values[0]) if 'id' in cmdKeys else None

        if selected_id:
            if selected_id in actives:
                sequence_id = selected_id
            else:
                raise exception.SequenceIdentificationFailure(f'{selected_id} is not active, '
                                                              f'actives({",".join(map(str, actives))})')
        # if id is not provided but only one sequence is active I can still figure out.
        else:
            if len(actives) > 1:
                raise exception.SequenceIdentificationFailure('multiple sequences are active, need to provide an id.')
            else:
                [sequence_id] = actives

        return self[sequence_id]
