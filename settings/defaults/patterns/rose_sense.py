# RoseSense (v19), ported from the original's gather patterns.
# Size and width are not used. The pattern runs from modules.misc.sense_patterns.
from modules.misc.sense_patterns import RoseSense

if "rose_sense" not in globals():
    rose_sense = RoseSense(self, tcfbkey, tclrkey, afcfbkey, afclrkey, rotup, sc_space)
rose_sense.run()


def onGatherEnd():
    rose_sense.finish()
