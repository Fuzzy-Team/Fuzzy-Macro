# PepperSense (v19), ported from Zenith Macro's gather patterns.
# Size and width are not used. The pattern runs from modules.misc.sense_patterns.
from modules.misc.sense_patterns import PepperSense

if "pepper_sense" not in globals():
    pepper_sense = PepperSense(self, tcfbkey, tclrkey, afcfbkey, afclrkey, rotup, sc_space)
pepper_sense.run()


def onGatherEnd():
    pepper_sense.finish()
