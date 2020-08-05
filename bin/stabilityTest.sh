#!/bin/bash

. /software/ics_launch/bin/setup.sh
setup -v tron_actorcore

$TRON_ACTORCORE_DIR/bin/oneCmd.py iic bias duplicate=3 comments='stabilityTest'
printf '\n'
$TRON_ACTORCORE_DIR/bin/oneCmd.py iic expose flat halogen=3.0 duplicate=3 cams=r1 comments='stabilityTest'
printf '\n'
$TRON_ACTORCORE_DIR/bin/oneCmd.py iic expose flat halogen=30.0 duplicate=3 cams=b1 comments='stabilityTest'
printf '\n'
$TRON_ACTORCORE_DIR/bin/oneCmd.py iic expose arc argon=20.0 neon=3 krypton=20 duplicate=3 comments='stabilityTest'
printf '\n\n'
$TRON_ACTORCORE_DIR/bin/oneCmd.py iic dark exptime=300 duplicate=5 comments='stabilityTest'
printf '\n'
