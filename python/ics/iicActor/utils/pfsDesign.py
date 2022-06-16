import pfs.utils.ingestPfsDesign as ingestPfsDesign
from ics.utils.opdb import opDB
from pfs.datamodel import PfsDesign


class PfsDesignHandler(object):

    @staticmethod
    def declareCurrent(cmd, visitor, designId=None):
        """ """
        designId = cmd.cmd.keywords['designId'].values[0] if designId is None else designId
        # declaring new field
        pfsDesign, visit0 = visitor.declareNewField(designId)
        # still generating that key for header/drp for now.
        cmd.inform('designId=0x%016x' % designId)
        # ingesting into opdb
        PfsDesignHandler.ingest(cmd, pfsDesign, to_be_observed_at="now")
        return pfsDesign, visit0

    @staticmethod
    def ingest(cmd, pfsDesign, designed_at=None, to_be_observed_at=None):
        """Inserting into opdb."""
        isNew = not opDB.fetchone(f'select pfs_design_id from pfs_design where pfs_design_id={pfsDesign.pfsDesignId}')

        if isNew:
            try:
                ingestPfsDesign.ingestPfsDesign(pfsDesign, designed_at=designed_at, to_be_observed_at=to_be_observed_at)
                cmd.inform('text="pfsDesign-0x%016x successfully inserted in opdb !"' % pfsDesign.pfsDesignId)
            except Exception as e:
                cmd.warn(f'text="ingestPfsDesign failed with {str(e)}, ignoring for now..."')
        else:
            cmd.warn('text="pfsDesign-0x%016x already inserted in opdb..."' % pfsDesign.pfsDesignId)

    @staticmethod
    def read(pfsDesignId, dirName):
        """Read PfsDesign from pfsDesignId"""
        return PfsDesign.read(pfsDesignId, dirName=dirName)
