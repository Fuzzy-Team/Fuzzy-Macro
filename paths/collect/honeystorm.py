# Navigate to honey storm location and summon it
# Credit to laganyt for the path
import sys
import os
# Add src to path if not already there
src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)
from modules import macro
from datetime import timedelta
objectiveData = macro.mergedCollectData["honeystorm"]
cooldownSeconds = objectiveData[2]

self.runPath("collect/stockings")
self.keyboard.walk("a",1.25, False)
self.keyboard.walk("s",1.5)
self.keyboard.walk("d",0.45)
self.keyboard.walk("s",0.8)
time.sleep(0.5)

