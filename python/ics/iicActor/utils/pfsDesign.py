import pfs.utils.ingestPfsDesign as ingestPfsDesign
from ics.utils.opdb import opDB
from pfs.datamodel import PfsDesign


class PfsDesignHandler(object):

    @staticmethod
    def declareCurrent(cmd, visitor, designId=None, variant=0):
        """ """
        cmdKeys = cmd.cmd.keywords
        designId = cmdKeys['designId'].values[0] if designId is None else designId
        variant = cmdKeys['variant'].values[0] if 'variant' in cmdKeys else variant

        # get actual pfsDesignId from designId0 and variant.
        if variant:
            designId = PfsDesignHandler.designIdFromVariant(designId0=designId, variant=variant)

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

    @staticmethod
    def latestDesignIdMatchingName(designName):
        """Retrieve last designId matching the name"""
        # retrieving designId from opdb
        sql = f"select pfs_design_id from pfs_design where substring(design_name,1,{len(designName)})='{designName}'"

        try:
            # not very clean but it's all I can do for now.
            allDesign = opDB.fetchall(sql)
            [designId] = allDesign[-1]
        except:
            raise RuntimeError(f'could not retrieve {designName} designId from opdb')

        return designId

    @staticmethod
    def designIdFromVariant(designId0, variant):
        """Retrieve actual designId from designId0 and variant"""

        fetched = opDB.fetchone(
            f'select pfs_design_id from pfs_design where design_id0={designId0} and variant={variant}')
        if not fetched:
            raise ValueError(f'could not retrieve variant {variant} where design_id0={designId0}')

        [designId] = fetched

        return designId

    @staticmethod
    def maxVariantMatchingDesignId0(designId0):
        """Retrieve actual designId from designId0 and variant"""

        fetched = opDB.fetchone(f'select max(variant) from pfs_design where design_id0={designId0}')
        if not fetched:
            raise ValueError(f'could not retrieve pfs_design where design_id0={designId0}')

        [maxVariant] = fetched

        return maxVariant

    @staticmethod
    def getVariants(designId0):
        return opDB.fetchall(f'select pfs_design_id,variant from pfs_design where design_id0={designId0}')
