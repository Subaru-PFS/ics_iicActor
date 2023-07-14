import numpy as np
import pandas as pd
from pfs.datamodel.pfsConfig import PfsDesign
from pfs.datamodel.utils import calculate_pfsDesignId
from pfs.utils.fiberids import FiberIds

fakeRa, fakeDec = 100, -89

def fakePfiNominal(fiberId):
    """Fake PfiNominal from fiberId, basically take x,y from GFM."""
    gfm = pd.DataFrame(FiberIds().data)
    # faking ra and dec from x,y
    x = gfm[gfm.fiberId.isin(fiberId)].x.to_numpy()
    y = gfm[gfm.fiberId.isin(fiberId)].y.to_numpy()

    return np.vstack((x, y)).transpose()


def fakeDesignIFromFiberId(fiberId, pfiNominal):
    """Fake ra and dec from pfiNominal and re-calculate pfsDesignId."""
    ra = fakeRa + 1e-3 * pfiNominal[:, 0]
    dec = fakeDec + 1e-3 * pfiNominal[:, 1]

    pfsDesignId = calculate_pfsDesignId(fiberId, ra, dec)

    return dict(pfsDesignId=pfsDesignId, ra=ra, dec=dec)


def sortFieldsByFiberId(kwargs):
    """Sort all PfsDesign fields eg list + np.array by fiberId."""

    def sortListOrArrayByIndex(array, sortedIndex):
        if isinstance(array, list):
            sortedArray = [array[i] for i in sortedIndex]
        elif isinstance(array, np.ndarray):
            sortedArray = array[sortedIndex]
        else:
            sortedArray = array

        return sortedArray

    keywords = PfsDesign._keywords + PfsDesign._scalars + ['fiberStatus']
    sortedIndex = np.argsort(kwargs['fiberId'])

    for keyword in keywords:
        kwargs[keyword] = sortListOrArrayByIndex(kwargs[keyword], sortedIndex)

    return kwargs


def mergeSuNSSAndDcb(pfsDesigns, designName):
    """Merge SuNSS and DCB PfsDesign."""
    kwargs = dict(pfsDesignId=0, raBoresight=fakeRa, decBoresight=fakeDec, posAng=0, arms='brn', guideStars=None,
                  designName=designName, variant=0, designId0=0)
    keywords = PfsDesign._keywords + PfsDesign._scalars + ['fiberStatus']

    # Just append field on top of each other.
    for design in pfsDesigns:
        for keyword in keywords:
            array = getattr(design, keyword)

            # no need to merge yet.
            if keyword not in kwargs:
                kwargs[keyword] = array
                continue

            if isinstance(array, list):
                kwargs[keyword].extend(array)
            elif isinstance(array, np.ndarray):
                kwargs[keyword] = np.append(kwargs[keyword], array, axis=0)
            else:
                pass

    # Recalculate pfsDesignId from fiberId and pfiNominal.
    kwargs.update(fakeDesignIFromFiberId(kwargs['fiberId'], kwargs['pfiNominal']))
    # Sort PfsDesign fields by fiberId.
    kwargs = sortFieldsByFiberId(kwargs)
    # Just return the constructed PfsDesign.
    return PfsDesign(**kwargs)
