import pfs.utils.ingestPfsDesign as ingestPfsDesign
from ics.utils.opdb import opDB


class PfsDesignHandler(object):

    @staticmethod
    def declareCurrentPfsDesign(cmd, visitor, designId=None):
        """ """
        designId = cmd.cmd.keywords['designId'].values[0] if designId is None else designId
        # declaring new field
        pfsDesign, visit0 = visitor.declareNewField(designId)
        # still generating that key for header/drp for now.
        cmd.inform('designId=Ox%016x' % designId)
        # ingesting into opdb
        PfsDesignHandler.ingestPfsDesign(cmd, pfsDesign)
        return pfsDesign, visit0

    @staticmethod
    def ingestPfsDesign(cmd, pfsDesign):
        """Inserting into opdb."""
        isNew = not opDB.fetchone(f'select pfs_design_id from pfs_design where pfs_design_id={pfsDesign.pfsDesignId}')

        if isNew:
            try:
                ingestPfsDesign.ingestPfsDesign(pfsDesign, to_be_observed_at='now')
            except Exception as e:
                cmd.warn(f'text="ingestPfsDesign failed with {str(e)}, ignoring for now..."')
        else:
            cmd.warn('text="pfsDesign(0x%016x) already inserted in opdb..."' % pfsDesign.pfsDesignId)
