"""Names available to custom gather patterns and stump snail patterns.

Pattern files run with these names as globals. Removing or renaming one can break
a user's pattern file, so treat this list as a public interface.
"""
import modules.screen.ocr as ocr
import modules.misc.appManager as appManager
import modules.misc.settingsManager as settingsManager
import pyautogui as pag
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP, benchmarkMSS, mssScreenshotPillowRGBA
from modules.controls.keyboard import keyboard
from modules.controls.sleep import (
    sleep,
    set_run_state,
    pauseable_sleep,
    set_resume_callback,
    set_interrupt_action,
    get_interrupt_action,
    InterruptRequested,
    INTERRUPT_NONE,
    INTERRUPT_STICKER_SPROUT,
)
import modules.controls.mouse as mouse
import modules.logging.log as logModule
from modules.submacros.fieldDriftCompensation import fieldDriftCompensation as fieldDriftCompensationClass
from modules.screen.robloxWindow import RobloxWindowBounds
import sys
import platform
import os
import re
import numpy as np
import threading
from modules.submacros.backpack import bpc
from modules.screen.imageSearch import *
from pynput.keyboard import Controller
import cv2
from modules.screen.color_check import get_sample_colors, percent_pixels_similar_to_color
from datetime import timedelta, datetime, timezone
from modules.misc.imageManipulation import *
from PIL import Image
from modules.misc import messageBox
from modules.submacros.memoryMatch import MemoryMatch
import math
import ast
from modules.reports.buffs import BUFF_RENDER_CONFIG, BuffDetector
from modules.reports.hourly import HourlyReport
from modules.reports.item_monitor import ItemMonitor
from modules.submacros.tadAltSync import TadAltSync
from modules.reports.live_gather import LiveGatherReport, LiveQuestProgressReport
from difflib import SequenceMatcher
import fuzzywuzzy.process
import fuzzywuzzy
import traceback
import pygetwindow as gw
from modules.submacros.hasteCompensation import HasteCompensationRevamped
from modules import bitmap_matcher
from modules.gather_session import GatherPatternRunner, GatherSession
import json
from modules.controls.sleep import pause_aware_time as time
from modules.macro.game_data import *

pynputKeyboard = Controller()
