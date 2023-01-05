import numpy as np
import pandas as pd
from pfs.datamodel.pfsConfig import PfsDesign
from pfs.datamodel.utils import calculate_pfsDesignId
from pfs.utils.fiberids import FiberIds

gfm = pd.DataFrame(FiberIds().data)


def fakeDesignIFromFiberId(fiberId):
    """"""
    # faking ra and dec from x,y

    x = gfm[gfm.fiberId.isin(fiberId)].x.to_numpy()
    y = gfm[gfm.fiberId.isin(fiberId)].y.to_numpy()

    ra = 100 + 1e-3 * x
    dec = 100 + 1e-3 * y

    pfiNominal = np.vstack((x, y)).transpose()
    pfsDesignId = calculate_pfsDesignId(fiberId, ra, dec)

    return dict(pfsDesignId=pfsDesignId, ra=ra, dec=dec, pfiNominal=pfiNominal)


def mergeSunssAndDcbDesign(designToMerge):
    """"""
    kwargs = dict(pfsDesignId=0, raBoresight=100, decBoresight=100, posAng=0, arms='brn', guideStars=None,
                  designName="", variant=0, designId0=0)
    keywords = PfsDesign._keywords + PfsDesign._scalars + ['fiberStatus']

    for design in designToMerge:
        for keyword in keywords:
            array = getattr(design, keyword)

            # no need to merge yet.
            if keyword not in kwargs:
                kwargs[keyword] = array
                continue

            if isinstance(array, list):
                kwargs[keyword].extend(array)
            elif isinstance(array, np.ndarray):
                if len(array.shape) > 1:
                    continue
                kwargs[keyword] = np.append(kwargs[keyword], array)
            else:
                pass

    kwargs.update(fakeDesignIFromFiberId(kwargs['fiberId']))
    merged = PfsDesign(**kwargs)
    return merged
