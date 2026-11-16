"""The commands the ag sequences send, spelled as ag takes them: designId, exptime, visit."""
import types

from ics.iicActor.sequenceList.ag import AcquireField, AutoguideStart, FocusSweep

DESIGN_ID = 1234567890123456789
# The names ag had for designId, exptime and visit; it no longer accepts them.
FORMER_NAMES = ('design_id=', 'exposure_time=', 'visit_id=')


def sent(sequence, visitId=7):
    """The commands of `sequence`, as sent once it holds visit `visitId`."""
    sequence.visit = types.SimpleNamespace(visitId=visitId)
    return [subCmd.fullCmd for subCmd in sequence]


def test_acquireField():
    """The design, exposure time and visit go to ag under the names iic itself takes them."""
    sequence = AcquireField(designId=DESIGN_ID, exptime=2000, guide='no', magnitude=20.0, dryRun='yes',
                            fit_dScale='yes', fit_dInR='no', exposure_delay=100, tec_off='yes', visit0=6)
    cmd, = sent(sequence)
    assert cmd == (f'ag acquire_field designId={DESIGN_ID} exptime=2000 guide=no magnitude=20.0 dry_run=yes '
                   'fit_dscale=yes fit_dinr=no exposure_delay=100 tec_off=yes visit0=6 visit=7')
    # Negative control: none of the names ag used to have.
    assert not [name for name in FORMER_NAMES if name in cmd]


def test_acquireFieldLeavesOutWhatIsNotGiven():
    """An option that was not given, and a visit0 that is not known, are not sent."""
    sequence = AcquireField(designId=DESIGN_ID, exptime=None, guide=None, magnitude=None, dryRun=None,
                            fit_dScale='yes', fit_dInR='yes', exposure_delay=None, tec_off=None, visit0=False)
    assert sent(sequence) == [f'ag acquire_field designId={DESIGN_ID} fit_dscale=yes fit_dinr=yes visit=7']


def test_autoguideStart():
    sequence = AutoguideStart(designId=DESIGN_ID, fromSky='yes', exptime=2000, cadence=5000,
                              center=[10.0, 20.0, 0.0], magnitude=20.0, dryRun='yes', fit_dScale='yes',
                              fit_dInR='no', exposure_delay=100, tec_off='yes', max_correction=10.0, visit0=6,
                              filter_bad_shape='yes')
    cmd, = sent(sequence)
    assert cmd == (f'ag autoguide start designId={DESIGN_ID} exptime=2000 cadence=5000 center=10.0,20.0,0.0 '
                   'magnitude=20.0 from_sky=yes dry_run=yes fit_dscale=yes fit_dinr=no exposure_delay=100 '
                   'tec_off=yes max_correction=10.0 visit0=6 filter_bad_shape=yes visit=7')
    # Negative control: none of the names ag used to have.
    assert not [name for name in FORMER_NAMES if name in cmd]


def test_focusSweepPosition():
    """Each focus position is an acquire_field on the sweep's visit."""
    sequence = FocusSweep(designId=DESIGN_ID, exptime=2000, fit_dScale='yes', fit_dInR='no',
                          exposure_delay=None, tec_off=None)
    sequence.addPosition()
    sequence.addPosition()
    cmd = f'ag acquire_field designId={DESIGN_ID} exptime=2000 fit_dScale=yes fit_dInR=no visit=7'
    assert sent(sequence) == [cmd, cmd]
    # Negative control: none of the names ag used to have.
    assert not [name for name in FORMER_NAMES if name in cmd]
