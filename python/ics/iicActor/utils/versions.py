import pfs.utils.versions as versionsUtils

__all__ = ("collectVersions",)


def collectVersions(models=None):
    """Collect software versions."""
    versions = versionsUtils.collectVersions(['ics_iicActor', 'pfs_instdata', 'pfs_utils',
                                              'datamodel', 'spt_operational_database'])
    versions['author'] = "iic"

    if models is not None:
        try:
            spsVersion = models['sps'].keyVarDict['version'].getValue()
        except ValueError:
            spsVersion = None

        versions['ics_spsActor'] = spsVersion

    return versions
