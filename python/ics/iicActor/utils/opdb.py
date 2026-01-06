import logging
import time

import ics.iicActor.utils.lib as iicUtils
import pandas as pd
import pfs.utils.ingestPfsDesign as ingestPfsDesign
from ics.iicActor.utils import exception
from pfs.utils.database import opdb


class OpdbHandler:
    def __init__(self, engine):
        self.engine = engine
        self.opdb = opdb.OpDB()

    def fetchone(self, sql):
        try:
            df = self.opdb.query_dataframe(sql)
        except Exception as e:
            raise exception.OpDBFailure(iicUtils.stripQuotes(str(e)))

        return df.squeeze()

    def fetchLastSequenceId(self):
        """Get last sequence_id FROM iic_sequence table."""
        sequence_id = self.fetchone('SELECT max(iic_sequence_id) FROM iic_sequence')
        sequence_id = 0 if sequence_id is None else sequence_id
        return int(sequence_id)

    def fetchLastGroupId(self):
        """Get last group_id FROM sequence_group table."""
        group_id = self.fetchone('SELECT max(group_id) FROM sequence_group')
        group_id = 0 if group_id is None else group_id
        return int(group_id)

    def fetchLastGroupIdMatchingName(self, group_name):
        """Get last group_id FROM sequence_group table matching group_name."""
        group_id = self.fetchone(f"SELECT max(group_id) FROM sequence_group WHERE group_name='{group_name}'")
        # something went wrong here
        if not group_id:
            raise exception.OpDBFailure(f'no sequence_group match group_name: {group_name}')

        return int(group_id)

    def getGroupNameFromGroupId(self, group_id):
        """
        Retrieve the group_name from the sequence_group table for a given group_id.

        Parameters
        ----------
        group_id : int
            The group_id to look up.

        Returns
        -------
        str
            The corresponding group_name.

        Raises
        ------
        exception.OpDBFailure
            If no matching group_name is found for the given group_id.
        """
        group_name = self.fetchone(f"SELECT group_name FROM sequence_group WHERE group_id={int(group_id)}")

        if not group_name:
            raise exception.OpDBFailure(f'No group_name found for group_id: {group_id}')

        return str(group_name)

    def getDeltaINSROT(self, visit0, spsVisitId):
        """Compute the difference in INSROT (instrument rotation) between spsVisit and visit0."""
        INSROT0 = self.fetchone(
            f"SELECT insrot FROM tel_status WHERE pfs_visit_id={visit0} and caller='mcs' ORDER BY status_sequence_id DESC LIMIT 1")
        INSROT = self.fetchone(
            f"SELECT insrot FROM tel_status WHERE pfs_visit_id={spsVisitId} ORDER BY status_sequence_id DESC LIMIT 1")
        return float(INSROT - INSROT0)

    def insert(self, table, **kwargs):
        """Simple insert into opDB, raising proper IicException."""
        df = pd.DataFrame(dict([(k, [v]) for k, v in kwargs.items()]))

        try:
            self.opdb.insert_dataframe(table, df=df)
        except Exception as e:
            raise exception.OpdbInsertFailed(table, e)

    def insertSequence(self, group_id, sequence_type, name, comments, cmd_str, doRetry=True, waitBetweenAttempt=1):
        """Insert into iic_sequence table. """
        # new_sequence_id = last + 1
        new_sequence_id = self.fetchLastSequenceId() + 1
        kwargs = dict(iic_sequence_id=int(new_sequence_id), group_id=group_id,
                      sequence_type=str(sequence_type), name=str(name), comments=str(comments), cmd_str=str(cmd_str),
                      created_at=pd.Timestamp.now())

        df = pd.DataFrame(dict([(k, [v]) for k, v in kwargs.items()]))
        df["group_id"] = pd.Series(df["group_id"], dtype="Int64")

        try:
            self.opdb.insert_dataframe('iic_sequence', df)
        # concurrent insert can fail.
        except Exception as e:
            if doRetry:
                time.sleep(waitBetweenAttempt)
                return self.insertSequence(group_id, sequence_type, name, comments, cmd_str, doRetry=False)

            raise exception.OpdbInsertFailed('iic_sequence', e)

        return new_sequence_id

    def insertVisitSet(self, caller, pfs_visit_id, sequence_id):
        """Insert into visit_set table."""

        def exposureTablePopulated():
            """Check is there is a matching visit in exposure table."""
            return not self.opdb.query_dataframe(f'SELECT pfs_visit_id FROM {exposure_table} WHERE pfs_visit_id={pfs_visit_id}').empty

        def visitSetPopulated():
            """Check if visit_set table is already populated."""
            return not self.opdb.query_dataframe(f'SELECT pfs_visit_id FROM visit_set WHERE pfs_visit_id={pfs_visit_id}').empty

        # AG commands are ignored when it comes to visit_set, with the current database design there can be ONLY ONE
        # iic_sequence_id per pfs_visit_id, so I choose to give the priority to sps/fps sequence
        # agFocusSweep is the only exception, in that case agFocusSweep is passed as caller to bypass that rule.
        if caller == 'ag':
            return

        tables = dict(sps='sps_exposure', fps='mcs_exposure', mcs='mcs_exposure', ag='agc_exposure')

        # agFocusSweep is the only exception.
        tables['agFocusSweep'] = tables['ag']

        exposure_table = tables[caller]

        if not exposureTablePopulated():
            logging.warning(f'no entry for {exposure_table}.pfs_visit_id={pfs_visit_id}.')
            return

        if visitSetPopulated():
            logging.info(f'caller={caller} visit_set.pfs_visit_id={pfs_visit_id} already exists...')
            return

        self.insert('visit_set', pfs_visit_id=int(pfs_visit_id), iic_sequence_id=int(sequence_id))

    def insertSequenceStatus(self, sequence_id, status):
        """Insert into iic_sequence_status table."""
        self.insert('iic_sequence_status', iic_sequence_id=int(sequence_id), finished_at=pd.Timestamp.now(),
                    **status.toOpDB())

    def insertSequenceGroup(self, group_name):
        """Insert into sequence_group table. """
        # new_group_id = last + 1
        new_group_id = self.fetchLastGroupId() + 1
        self.insert('sequence_group', group_id=int(new_group_id), group_name=group_name, created_at=pd.Timestamp.now())
        return new_group_id

    def insertPfsConfigSps(self, pfs_visit_id, visit0, camMask, instStatusFlag):
        """Insert into pfs_config_sps table."""
        self.insert('pfs_config_sps', pfs_visit_id=int(pfs_visit_id), visit0=int(visit0),
                    cam_mask=camMask, inst_status_flag=int(instStatusFlag))

    def ingest(self, cmd, pfsDesign, designed_at=None):
        """Inserting into opdb."""
        isNew = self.fetchone(f'select pfs_design_id from pfs_design where pfs_design_id={pfsDesign.pfsDesignId}').empty

        if isNew:
            try:
                ingestPfsDesign.ingestPfsDesign(pfsDesign, designed_at=designed_at)
                cmd.inform('text="pfsDesign-0x%016x successfully inserted in opdb !"' % pfsDesign.pfsDesignId)
            except Exception as e:
                cmd.warn(f'text="ingestPfsDesign failed with {str(e)}, ignoring for now..."')
        else:
            cmd.warn('text="pfsDesign-0x%016x already inserted in opdb..."' % pfsDesign.pfsDesignId)

    def latestDesignIdMatchingName(self, designName, exact=False):
        """Retrieve last designId matching the name"""
        # be strict about the name if exact==True
        condition = f"design_name='{designName}'" if exact else f"substring(design_name,1,{len(designName)})='{designName}'"
        sql = f"select pfs_design_id from pfs_design where {condition} order by to_be_observed_at desc limit 1"

        df = self.opdb.query_dataframe(sql)

        if df.empty:
            raise RuntimeError(f'could not retrieve {designName} designId from opdb')

        return df.pfs_design_id.iloc[0]

    def designIdFromVariant(self, designId0, variant):
        """Retrieve actual designId from designId0 and variant"""
        designId = self.fetchone(
            f'select pfs_design_id from pfs_design where design_id0={designId0} and variant={variant}')

        if designId.empty:
            raise ValueError(f'could not retrieve variant {variant} where design_id0={designId0}')

        return designId

    def maxVariantMatchingDesignId0(self, designId0):
        """Retrieve actual designId from designId0 and variant"""
        maxVariant = self.fetchone(f'select max(variant) from pfs_design where design_id0={designId0}')

        if maxVariant.empty:
            raise ValueError(f'could not retrieve pfs_design where design_id0={designId0}')

        return maxVariant

    def getAllVariants(self, designId0):
        return self.opdb.query_dataframe(f'select pfs_design_id,variant from pfs_design where design_id0={designId0}')
