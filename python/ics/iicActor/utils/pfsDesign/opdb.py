import pfs.utils.ingestPfsDesign as ingestPfsDesign
from ics.utils.opdb import opDB


def ingest(cmd, pfsDesign, designed_at=None):
    """Inserting into opdb."""
    isNew = not opDB.fetchone(f'select pfs_design_id from pfs_design where pfs_design_id={pfsDesign.pfsDesignId}')

    if isNew:
        try:
            ingestPfsDesign.ingestPfsDesign(pfsDesign, designed_at=designed_at)
            cmd.inform('text="pfsDesign-0x%016x successfully inserted in opdb !"' % pfsDesign.pfsDesignId)
        except Exception as e:
            cmd.warn(f'text="ingestPfsDesign failed with {str(e)}, ignoring for now..."')
    else:
        cmd.warn('text="pfsDesign-0x%016x already inserted in opdb..."' % pfsDesign.pfsDesignId)


def latestDesignIdMatchingName(designName, exact=False):
    """Retrieve last designId matching the name"""
    # be strict about the name if exact==True
    condition = f"design_name='{designName}'" if exact else f"substring(design_name,1,{len(designName)})='{designName}'"
    sql = f"select pfs_design_id from pfs_design where {condition} order by to_be_observed_at desc limit 1"

    try:
        # not very clean, but it's all I can do for now.
        [designId] = opDB.fetchone(sql)
    except:
        raise RuntimeError(f'could not retrieve {designName} designId from opdb')

    return designId


def designIdFromVariant(designId0, variant):
    """Retrieve actual designId from designId0 and variant"""
    fetched = opDB.fetchone(f'select pfs_design_id from pfs_design where design_id0={designId0} and variant={variant}')

    if not fetched:
        raise ValueError(f'could not retrieve variant {variant} where design_id0={designId0}')

    [designId] = fetched

    return designId


def maxVariantMatchingDesignId0(designId0):
    """Retrieve actual designId from designId0 and variant"""
    fetched = opDB.fetchone(f'select max(variant) from pfs_design where design_id0={designId0}')

    if not fetched:
        raise ValueError(f'could not retrieve pfs_design where design_id0={designId0}')

    [maxVariant] = fetched

    return maxVariant


def getAllVariants(designId0):
    return opDB.fetchall(f'select pfs_design_id,variant from pfs_design where design_id0={designId0}')
