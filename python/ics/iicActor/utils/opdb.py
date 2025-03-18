import logging

import iicActor.utils.lib as iicUtils
from ics.utils.opdb import opDB
from iicActor.utils import exception
import psycopg2
import time


def fetchOneEntry(query):
    try:
        oneEntry, = opDB.fetchone(query)
    except Exception as e:
        raise exception.OpDBFailure(iicUtils.stripQuotes(str(e)))

    return oneEntry


def fetchLastSequenceId():
    """Get last sequence_id FROM iic_sequence table."""
    sequence_id = fetchOneEntry('SELECT max(iic_sequence_id) FROM iic_sequence')
    sequence_id = 0 if sequence_id is None else sequence_id
    return int(sequence_id)


def fetchLastGroupId():
    """Get last group_id FROM sequence_group table."""
    group_id = fetchOneEntry('SELECT max(group_id) FROM sequence_group')
    group_id = 0 if group_id is None else group_id
    return int(group_id)


def fetchLastGroupIdMatchingName(group_name):
    """Get last group_id FROM sequence_group table matching group_name."""
    group_id = fetchOneEntry(f"SELECT max(group_id) FROM sequence_group WHERE group_name='{group_name}'")
    # something went wrong here
    if not group_id:
        raise exception.OpDBFailure(f'no sequence_group match group_name: {group_name}')

    return int(group_id)

def getDeltaINSROT(visit0, spsVisitId):
    """Compute the difference in INSROT (instrument rotation) between spsVisit and visit0."""
    INSROT0 = fetchOneEntry(f"SELECT insrot FROM tel_status WHERE pfs_visit_id={visit0} and caller='mcs' ORDER BY status_sequence_id DESC LIMIT 1")
    INSROT = fetchOneEntry(f"SELECT insrot FROM tel_status WHERE pfs_visit_id={spsVisitId} ORDER BY status_sequence_id DESC LIMIT 1")
    return float(INSROT-INSROT0)

def insertIntoOpDB(tablename, **kwargs):
    """Simple insert into opDB, raising proper IicException."""
    try:
        opDB.insert(tablename, **kwargs)
    except Exception as e:
        raise exception.OpdbInsertFailed(tablename, e)


def insertSequence(group_id, sequence_type, name, comments, cmd_str, doRetry=True, waitBetweenAttempt=1):
    """Insert into iic_sequence table. """
    # new_sequence_id = last + 1
    new_sequence_id = fetchLastSequenceId() + 1

    try:
        opDB.insert('iic_sequence', iic_sequence_id=new_sequence_id, group_id=group_id,
                    sequence_type=sequence_type,  name=name, comments=comments, cmd_str=cmd_str,
                    created_at='now')
    # concurrent insert can fail.
    except psycopg2.errors.UniqueViolation as e:
        if doRetry:
            time.sleep(waitBetweenAttempt)
            return insertSequence(group_id, sequence_type, name, comments, cmd_str, doRetry=False)

        raise exception.OpdbInsertFailed('iic_sequence', e)

    return new_sequence_id


def insertVisitSet(caller, pfs_visit_id, sequence_id):
    """Insert into visit_set table."""
    tables = dict(sps='sps_exposure', fps='mcs_exposure', mcs='mcs_exposure', ag='agc_exposure')
    exposure_table = tables[caller]

    def exposureTablePopulated():
        """Check is there is a matching visit in exposure table."""
        return opDB.fetchone(f'SELECT pfs_visit_id FROM {exposure_table} WHERE pfs_visit_id={pfs_visit_id}')

    def visitSetAlreadyPopulated():
        """Check if visit_set table is already populated."""
        return opDB.fetchone(f'SELECT pfs_visit_id FROM visit_set WHERE pfs_visit_id={pfs_visit_id}')

    if not exposureTablePopulated():
        logging.warning(f'no entry for {exposure_table}.pfs_visit_id={pfs_visit_id}.')
        return

    if visitSetAlreadyPopulated():
        logging.info(f'caller={caller} visit_set.pfs_visit_id={pfs_visit_id} already exists...')
        return

    insertIntoOpDB('visit_set', pfs_visit_id=pfs_visit_id, iic_sequence_id=sequence_id)


def insertSequenceStatus(sequence_id, status):
    """Insert into iic_sequence_status table."""
    insertIntoOpDB('iic_sequence_status', iic_sequence_id=sequence_id, finished_at='now', **status.toOpDB())


def insertSequenceGroup(group_name):
    """Insert into sequence_group table. """
    # new_group_id = last + 1
    new_group_id = fetchLastGroupId() + 1
    insertIntoOpDB('sequence_group', group_id=new_group_id, group_name=group_name, created_at='now')
    return new_group_id


def insertPfsConfigSps(pfs_visit_id, visit0, camMask, instStatusFlag):
    """Insert into pfs_config_sps table."""
    insertIntoOpDB('pfs_config_sps', pfs_visit_id=pfs_visit_id, visit0=visit0,
                   cam_mask=camMask, inst_status_flag=instStatusFlag)
