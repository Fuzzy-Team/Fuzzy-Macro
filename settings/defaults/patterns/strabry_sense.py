# StrabrySense (v19), ported from the original's gather patterns.
# Size and width are not used. The pattern runs from modules.misc.sense_patterns.
from modules.misc.sense_patterns import StrabrySense

if "strabry_sense" not in globals():
    strabry_sense = StrabrySense(self, tcfbkey, tclrkey, afcfbkey, afclrkey, rotup, sc_space)
strabry_sense.run()


def onGatherEnd():
    strabry_sense.finish()
