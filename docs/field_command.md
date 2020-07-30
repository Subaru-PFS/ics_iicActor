# Interface for main Gen2-to-IIC observing command

This document only addresses the Gen2, telescope, and IIC command flow
for the single main Gen2 observing command.  As we have agreed
previously, PFS will provide engineering-mode access to all PFS
primitives.

We believe that we only need one top-level Gen2 command for normal
operations, and that all commands from Gen2 to IIC can be simple
synchronous commands.  Decisions about targetting, QA, and handling
failures (such as fail to acquire guide stars) will require human
intervention, but otherwise all steps of field acquisition and data
acquisistion can be automatically sequenced, allowing us to maximise
the time on target.

Three significant external systems are assumed, and are expected to have
their own GUIs and other interfaces:

- A QA system good enough to help decide when a running exposure is
  the last one for the field being observed, after which the observer
  will use a command like `IIC SPS fieldIsDone` to notify the
  instrument, allowing us to move to the next field.

- A targeting system which can provide the pfsDesign and coordinates
  for the next field to observe: `IIC target getNextField`.

- An AG control GUI, to monitor and control field acquisition and
  guiding. Specifically, this would give control over difficult field
  acquisitions and bad guide stars. For example, human intervention
  may be required when using PFS to study chemical evolution in the
  Galactic bulge

I do not give details for the Gen2->telescope commands, but will leave
that for people who know the details. Nor do I give internal details
on the IIC commands: those are discussed elsewhere.

## Pseudo-code

```
# Assume that either we are not yet observing, or that the QA system
# indicates that the running exposure is the last one for theis field.
# Assume that the next field has been selected in the targetting system.

Gen2_START_NEXT_FIELD
  # Get coordinates for next field. Once this command has been run,
  # ICC, the AG system, and the FPS also know what the field is.
  pfsDesign, RA, Dec, PA = IIC getNextField

  # Tell SPS that the running exposure (if any) is the last one for
  # this field. _Blocks_ until shutter closes (or returns immediately
  # if no exposure is active)
  IIC SPS finishField

  # Start cobra convergence, slew telescope to field.
  # One tricky bit here which I crudely flesh out. If the time to slew
  # the rotator is longer than the time to slew the telescope, do all
  # fine cobra moves after field acquisition: we do not gain any time by
  # turning off the rotator now.  But if the rotator slew finishes
  # first by an interesting amount, it does pay to stop the rotator
  # and make all but the last cobra move now.
  rotatorIsSlow = IIC getConvergenceStrategy(expectedSlewTimes)
  if rotatorisSlow
     parallel {
        IIC FPS coarseConvergence
        TEL slew RA Dec
        TEL slewRotator PA
     }
  else
     parallel {
        TEL slew RA Dec
        seq {
            parallel {
                IIC FPS coarseConvergence
                TEL slewRotator PA
            }
            TEL stopRotator
            IIC FPS continueConvergence
            TEL resumeRotator
        }
     }

  # Acquire field. Telescope axes are all moving.
  # Note that this might fail and would require manual attention via the AG GUI.
  IIC AG acquireField

  # Stop rotator, finish cobra convergence.
  TEL stopRotator
  IIC FPS finishConvergence

  # Restart rotator and allow AG to recenter and start guiding. Field
  # should be very close: the AG wlll probably only need a single
  # confirmation frame.
  TEL resumeRotator
  IIC AG startGuiding

  # Start science exposures. These will continue until "finishField"
  # is received or some planned limit is hit.
  IIC SPS startExposures
```

## Notes and questions

Some notes/questions:

- will we ever pause exposures? Does it make sense to given the H4s?

- I am assuming that "coarse" convergence means "what we can do with
  the rotator moving", which we do not quite know yet.

- for the field acquisition, is it better for the AG system to command
  the telescope, or should it return calculated (ra, dec, rot) offsets
  to Gen2?

- do we need to allow the targeting and qa systems to prepare/call the
  Gen2 command? [I think we can defer that.]
