import atexit
import ctypes
import eel
import multiprocessing
import pyautogui as pag
import signal
import subprocess
import sys
import time
from threading import Thread
import modules.controls.mouse as mouse
import modules.macro as macroModule
from modules.controls.hotkeys import watch_for_hotkeys
from modules.controls.sleep import INTERRUPT_NONE
from modules.discord_bot.richPresence import RichPresenceManager
from modules.misc import messageBox
from modules.misc.ColorProfile import DisplayColorProfile
from modules.misc.appManager import getWindowSize
from modules.misc.imageManipulation import adjustImage
from modules.screen.imageSearch import locateImageOnScreen
from modules.reports.hourly import HourlyReport
from modules.submacros.tadAltSync import TadAltSync


def millify(n):
    """Format large numbers with suffixes"""
    for limit, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= limit:
            return f"{n/limit:.1f}{suffix}"
    return str(int(n))


def runApp(macroTarget):
    print("Loading gui...")
    import gui
    import modules.screen.screenData as screenData
    from modules.controls.keyboard import keyboard as keyboardModule
    import modules.logging.log as logModule
    import modules.misc.appManager as appManager
    import modules.misc.settingsManager as settingsManager
    from modules.discord_bot.discordBot import discordBot
    from modules.submacros.convertAhkPattern import ahkPatternToPython
    from modules.submacros.stream import cloudflaredStream
    import os

    if sys.version_info[1] <= 7:
        print("start method set to spawn")
        multiprocessing.set_start_method("spawn")
    macroProc = None
    #set screen data
    screenData.setScreenData()
    screenInfo = screenData.getScreenData()
    #value to control if macro main loop is running
    #0: stop (terminate process)
    #1: start (start process)
    #2: already running (do nothing)
    #3: already stopped (do nothing)
    #4: disconnected (rejoin)
    manager = multiprocessing.Manager()
    run = manager.Value('i', 3)
    gui.setRunState(3)  # Initialize the global run state
    recentLogs = manager.list()  # Shared list to store recent log entries for discord bot
    gui.setRecentLogs(recentLogs)
    updateGUI = manager.Value('i', 0)
    skipTask = manager.Value('i', INTERRUPT_NONE)  # interrupt action for the running task
    skipServer = manager.Value('i', 0)  # one-shot request to abandon the active private-server join
    status = manager.Value(ctypes.c_wchar_p, "none")
    presence = manager.Value(ctypes.c_wchar_p, "")
    logQueue = manager.Queue()
    discordMessageQueue = manager.Queue()
    planterCommandQueue = manager.Queue()
    streamControlQueue = manager.Queue()
    pin_requests = manager.Queue()  # Shared queue for pin requests
    start_keyboard_listener_fn = watch_for_hotkeys(run)
    logger = logModule.log(logQueue, False, None, False, blocking=False, discordMessageQueue=discordMessageQueue)
    gui.configureToolRuntime(logger=logger, status=status, presence=presence)

    disconnectCooldownUntil = 0 #only for running disconnect check on low performance

    #add missing defaults to the current profile's files and apply migrations
    settingsManager.ensureRuntimeData()
    settingsManager.initializeMacroProfile()

    #convert ahk pattern
    patterns_dir = settingsManager.getPatternsDir()
    if os.path.exists(patterns_dir):
        ahkPatterns = [x for x in os.listdir(patterns_dir) if ".ahk" in x]
        for pattern in ahkPatterns:
            pattern_path = os.path.join(patterns_dir, pattern)
            with open(pattern_path, "r") as f:
                ahk = f.read()
            f.close()
            try:
                python = ahkPatternToPython(ahk)
                print(f"Converted: {pattern}")
                patternName = pattern.rsplit(".", 1)[0].lower()
                output_path = os.path.join(patterns_dir, f"{patternName}.py")
                with open(output_path, "w") as f:
                    f.write(python)
                f.close()
            except:
                messageBox.msgBox(title="Failed to convert pattern", text=f"There was an error converting {pattern}. The pattern will not be used.")
    
    #setup stream class
    stream = cloudflaredStream()

    def releaseInputsSafely():
        try:
            keyboardModule.releaseMovement()
        except pag.FailSafeException:
            print("PyAutoGUI fail-safe triggered while releasing movement during shutdown.")
        except Exception as e:
            print(f"Failed to release movement during shutdown: {e}")
        try:
            mouse.mouseUp()
        except pag.FailSafeException:
            print("PyAutoGUI fail-safe triggered while releasing mouse during shutdown.")
        except Exception as e:
            print(f"Failed to release mouse during shutdown: {e}")

    def onExit():
        try:
            stopApp()
        except Exception as e:
            print(f"Error during shutdown cleanup: {e}")
        # Reset timed bear quest states on exit so macro resumes checking next run
        try:
            settingsManager.saveSettingFile("brown_bear_quest_state", 0, settingsManager.getUserDataPath("timings.txt"))
        except Exception:
            pass
        try:
            settingsManager.saveSettingFile("black_bear_quest_state", 0, settingsManager.getUserDataPath("timings.txt"))
        except Exception:
            pass
        try:
            if discordBotProc and discordBotProc.is_alive():
                discordBotProc.terminate()
                discordBotProc.join()
        except NameError:
            pass
        try:
            if richPresenceManager:
                richPresenceManager.stop()
        except NameError:
            pass
        
    def stopApp(page= None, sockets = None):
        nonlocal macroProc
        releaseInputsSafely()
        releaseInputsSafely()
        #print(sockets)
        if macroProc and macroProc.is_alive():
            # Give the macro process a chance to observe run.value == 0 and run
            # gather cleanup hooks, including AI gather video finalization.
            stop_wait_deadline = time.time() + 1
            while macroProc.is_alive() and time.time() < stop_wait_deadline:
                releaseInputsSafely()
                releaseInputsSafely()
                macroProc.join(timeout=0.05)
        if macroProc and macroProc.is_alive():
            macroProc.terminate()
            macroProc.join(timeout=2)
            if macroProc.is_alive():
                macroProc.kill()
                macroProc.join(timeout=2)
        macroProc = None
        stream.stop()
        #if discordBotProc.is_alive(): discordBotProc.kill()
        releaseInputsSafely()
        releaseInputsSafely()
    
    def startMacroProcess():
        proc = multiprocessing.Process(target=macroTarget, args=(status, logQueue, updateGUI, run, skipTask, presence, discordMessageQueue, planterCommandQueue, skipServer), daemon=True)
        proc.start()
        return proc

    def showRunState(state):
        gui.setRunState(state)
        try:
            gui.toggleStartStop()
        except Exception:
            pass  # eel may not be ready yet

    atexit.register(onExit)
        
    #setup and launch gui
    gui.run = run
    gui.launch()
    # Ensure GUI loads current settings immediately on open (adds Brown Bear if missing)
    try:
        gui.updateGUI()
    except Exception:
        pass
    
    # Start keyboard listener after GUI launch to ensure it's on the main thread (required on macOS)
    # This prevents TIS/TSM errors on macOS
    if start_keyboard_listener_fn:
        try:
            start_keyboard_listener_fn()
            print("Keyboard listener started successfully")
        except Exception as e:
            print(f"Failed to start keyboard listener after GUI launch: {e}")
    
    #use run.value to control the macro loop

    #check color profile
    try:
        colorProfileManager = DisplayColorProfile()
        currentProfileColor = colorProfileManager.getCurrentColorProfile()
        if not "sRGB" in currentProfileColor:
            try:
                if messageBox.msgBoxOkCancel(title="Incorrect Color Profile", text=f"You current display's color profile is {currentProfileColor} but sRGB is required for the macro.\nPress 'Ok' to change color profiles"):
                    colorProfileManager.resetDisplayProfile()
                    colorProfileManager.setCustomProfile("/System/Library/ColorSync/Profiles/sRGB Profile.icc")
                    messageBox.msgBox(title="Color Profile Success", text="Successfully changed the current color profile to sRGB")

            except Exception as e:
                messageBox.msgBox(title="Failed to change color profile", text=e)
    except Exception:
        pass
    
    #check screen recording permissions
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        if not cg.CGRequestScreenCaptureAccess():
            messageBox.msgBox(title="Screen Recording Permission", text='Terminal does not have the screen recording permission. The macro will not work properly.\n\nTo fix it, go to System Settings -> Privacy and Security -> Screen Recording -> add and enable Terminal. After that, restart the macro')
    except AttributeError:
        pass
    #check full keyboard access
    try:
        result = subprocess.run(
            ["defaults", "read", "com.apple.universalaccess", "KeyboardAccessEnabled"],
            capture_output=True,
            text=True
        )
        value = result.stdout.strip()
        if value == "1":
            messageBox.msgBox(text = "Full Keyboard Access is enabled. The macro will not work properly\
                \nTo disable it, go to System Settings -> Accessibility -> Keyboard -> uncheck 'Full Keyboard Access'")
    except Exception as e:
        print("Error reading Full Keyboard Access:", e)

    discordBotProc = None
    prevDiscordBotToken = None
    prevRunState = run.value  # Track previous run state for GUI updates
    autoStopStartTime = None
    autoStopDeadline = None
    autoStopHours = 0.0
    
    # Initialize Rich Presence Manager
    richPresenceManager = None
    
    # Cache settings for main GUI loop to avoid reloading every 0.5 seconds
    gui_settings_cache = {}
    last_gui_settings_load = 0
    gui_settings_cache_duration = 1.0  # Reload settings every 1 second max

    def parseAutoStopHours(settings):
        try:
            hours = float(settings.get("auto_stop_after", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, hours)

    def startStreamIfNeeded(settings):
        if stream.streaming:
            return True

        def waitForStreamURL():
            #wait for up to 15 seconds for the public link
            for _ in range(150):
                time.sleep(0.1)
                if stream.publicURL:
                    logger.webhook("Stream Started", f'Stream URL: {stream.publicURL}', "purple", route_category="stream")

                    # If bot is enabled, request pinning of the stream message
                    if logModule.delivery_uses_bot_commands(settings) and settings.get("pin_stream_url", False):
                        import modules.logging.webhook as webhookModule
                        if webhookModule.last_channel_id:
                            try:
                                pin_requests.put({
                                    'channel_id': webhookModule.last_channel_id,
                                    'search_text': 'Stream URL'
                                })
                                print("Pin request queued for stream URL message")
                            except Exception as e:
                                print(f"Error queueing pin request: {e}")
                    return

            logger.webhook("", 'Stream could not start. Check terminal for more info', "red", ping_category="ping_critical_errors", route_category="stream")

        if stream.isCloudflaredInstalled():
            logger.webhook("", "Starting Stream...", "light blue", route_category="stream")
            stream.start(settings.get("stream_resolution", 0.75))
            Thread(target=waitForStreamURL, daemon=True).start()
            return True

        messageBox.msgBox(text='Cloudflared is required for streaming but is not installed. Visit https://fuzzy-team.gitbook.io/fuzzy-macro/discord-setup/stream-setup for installation instructions', title='Cloudflared not installed')
        return False

    def processStreamControlCommands(settings):
        while not streamControlQueue.empty():
            try:
                command = streamControlQueue.get_nowait()
            except Exception:
                break

            action = str(command.get("action", "")).lower()
            if action == "enable":
                if run.value in (2, 4, 6):
                    startStreamIfNeeded(settings)
            elif action == "disable":
                if stream.streaming:
                    stream.stop()
                    logger.webhook("Stream Stopped", "Stream disabled from Discord.", "orange", route_category="stream")
                else:
                    stream.stop()

    while True:
        eel.sleep(0.5)
        
        # Get cached settings
        current_time = time.time()
        if current_time - last_gui_settings_load > gui_settings_cache_duration:
            gui_settings_cache = settingsManager.loadAllSettings()
            last_gui_settings_load = current_time
        setdat = gui_settings_cache
        logger.enableWebhook = logModule.delivery_uses_webhook(setdat)
        logger.enableDiscordBot = logModule.delivery_uses_bot_messages(setdat)
        logger.webhookURL = logModule.get_default_delivery_route(setdat)
        logger.routeSettings = logModule.build_route_settings(setdat)
        logger.sendScreenshots = setdat.get("send_screenshot", True)
        logger.hourlyReportOnly = setdat.get("only_send_hourly_report", False)
        logger.enableDiscordPing = True
        logger.discordUserID = setdat.get("discord_user_id", "")
        logger.pingSettings = {
            key: value for key, value in setdat.items() if str(key).startswith("ping_")
        }
        processStreamControlCommands(setdat)

        if autoStopStartTime is not None and run.value in (2, 4, 6):
            latestAutoStopHours = parseAutoStopHours(setdat)
            if latestAutoStopHours != autoStopHours:
                autoStopHours = latestAutoStopHours
                autoStopDeadline = autoStopStartTime + (autoStopHours * 3600) if autoStopHours > 0 else None

        if autoStopDeadline is not None and run.value in (2, 4, 6) and current_time >= autoStopDeadline:
            logger.webhook(
                "Macro Auto Stopped",
                f"Stopped after {autoStopHours:g} hour{'s' if autoStopHours != 1 else ''}.",
                "orange",
                route_category="macro_status",
            )
            run.value = 0

        #discord bot. Look for changes in the bot token
        # Coerce to str: settings parser may turn digit-only values into ints
        currentDiscordBotToken = str(setdat.get("discord_bot_token") or "").strip()
        shouldRunDiscordBot = logModule.delivery_uses_bot_commands(setdat) and bool(currentDiscordBotToken)
        if shouldRunDiscordBot and currentDiscordBotToken != prevDiscordBotToken:
            if discordBotProc is not None and discordBotProc.is_alive():
                print("Detected change in discord bot token, killing previous bot process")
                discordBotProc.terminate()
                discordBotProc.join()
            discordBotProc = multiprocessing.Process(target=discordBot, args=(currentDiscordBotToken, run, status, skipTask, recentLogs, pin_requests, updateGUI, discordMessageQueue, planterCommandQueue, streamControlQueue, skipServer), daemon=True)
            prevDiscordBotToken = currentDiscordBotToken
            discordBotProc.start()
        elif not shouldRunDiscordBot and discordBotProc is not None and discordBotProc.is_alive():
            print("Discord bot mode disabled, stopping bot process")
            discordBotProc.terminate()
            discordBotProc.join()
            discordBotProc = None
            prevDiscordBotToken = None

        # Discord Rich Presence - Initialize and always show status
        discord_rp_enabled = setdat.get("discord_rich_presence", False)
        
        if richPresenceManager is None and discord_rp_enabled:
            # Initialize Rich Presence Manager
            richPresenceManager = RichPresenceManager(status, enabled=True, presence_value=presence)
            richPresenceManager.start()
            print("Discord Rich Presence started")
        elif richPresenceManager is not None:
            # Update settings if they changed
            richPresenceManager.set_enabled(discord_rp_enabled)
            
            # Update status based on macro run state
            if run.value == 0 or run.value == 3:  # Stopped
                # Clear any presence override and show "On main menu" when not running
                try:
                    if presence is not None:
                        presence.value = ""
                except Exception:
                    pass
                if status.value != "idle_main_menu":
                    status.value = "idle_main_menu"
            elif run.value == 6:  # Paused
                # Show "Paused" status
                if status.value != "paused":
                    status.value = "paused"

        # Check if run state changed
        if run.value != prevRunState:
            # Check for resume (transition from paused to running)
            if prevRunState == 6 and run.value == 2:
                try:
                    appManager.openApp("Roblox")
                except Exception:
                    pass
                logger.webhook("Macro Resumed", "Fuzzy Macro", "bright green", route_category="macro_status")
            # Check for pause (transition from running to paused)
            elif prevRunState == 2 and run.value == 6:
                keyboardModule.releaseMovement()
                mouse.mouseUp()
                logger.webhook("Macro Paused", "Use F2 or /resume to continue", "orange", route_category="macro_status")

            showRunState(run.value)
            prevRunState = run.value

        if run.value == 1:
            HourlyReport().resetAllStats()
            if setdat.get("enable_stream", False):
                startStreamIfNeeded(setdat)

            print("starting macro proc")
            #check if user enabled color-based field drift compensation but sprinkler is not supreme saturator
            #skip when using AI sprinkler model (works with any sprinkler)
            fieldSettings = settingsManager.loadFields()
            useAiDriftComp = setdat.get("use_sprinkler_model_for_drift_compensation", False)
            if not useAiDriftComp:
                for field in setdat.get("fields", []):
                    fs = fieldSettings.get(field, {})
                    if fs.get("field_drift_compensation", False) and setdat.get("sprinkler_type") != "saturator":
                        messageBox.msgBox(title="Field Drift Compensation", text=f"You have Field Drift Compensation enabled for {field} field, \
                                        but you do not have Supreme Saturator as your sprinkler type in configs.\n\
                                        Color-based Field Drift Compensation requires the Supreme Saturator.\n\
                                        Enable 'Use Sprinkler Model For Field Drift Compensation' in Config to use AI detection with any sprinkler, \
                                        or disable field drift compensation if you do not have the Supreme Saturator.")
                        break
            #check if blender is enabled but there are no items to craft
            validBlender = not setdat["blender_enable"] #valid blender set to false if blender is enabled, else its true since blender is disabled
            for i in range(1, macroModule.BLENDER_ITEM_SLOTS + 1):
                if setdat[f"blender_item_{i}"] != "none" and (setdat[f"blender_repeat_{i}"] or setdat[f"blender_repeat_inf_{i}"]):
                    validBlender = True
            if not validBlender:
                messageBox.msgBox(title="Blender", text="You have blender enabled, \
                                    but there are no more items left to craft.\n\
				                    Check the 'repeat' setting on your blender items and reset blender data.")
            #macro proc
            macroProc = startMacroProcess()

            macro_version = settingsManager.getMacroVersion()
            macro_mode = str(setdat.get("macro_mode", "normal") or "normal").strip().lower()
            mode_names = {
                "normal": "Normal Mode",
                "alt": "Alt Mode",
                "field": "Field Mode",
                "quest": "Quest Mode",
                "bug": "Bug Run Mode",
            }
            start_details = [
                f"Fuzzy Macro v{macro_version}",
                f"Mode: {mode_names.get(macro_mode, macro_mode.title())}",
            ]
            if macro_mode == "alt":
                if setdat.get("alt_mode_field_pending", False):
                    active_alt_field = str(setdat.get("alt_mode_field") or "").strip()
                    start_details.append(f"Alt Field: {active_alt_field.title() or 'Waiting for Host'}")
                else:
                    start_details.append("Alt Field: Waiting for Host")
            start_details.append(f'Display: {screenInfo["display_type"]}, {screenInfo["screen_width"]}x{screenInfo["screen_height"]}')
            logger.webhook("Macro Started", "\n".join(start_details), "purple", route_category="macro_status")
            run.value = 2
            autoStopStartTime = time.time()
            autoStopHours = parseAutoStopHours(setdat)
            autoStopDeadline = autoStopStartTime + (autoStopHours * 3600) if autoStopHours > 0 else None
            showRunState(2)
        elif run.value == 0:
            had_macro_proc = bool(macroProc)
            autoStopStartTime = None
            autoStopDeadline = None
            autoStopHours = 0.0

            # Stop macro/tools and release all inputs first.
            showRunState(0)

            if had_macro_proc:
                logger.webhook("Macro Stopped", "Fuzzy Macro", "red", route_category="macro_status")
                if setdat.get("macro_mode", "normal") != "alt":
                    TadAltSync(setdat, logger).initialize_alts()
            try:
                gui.stopAllTools()
            except Exception:
                pass

            stopApp()

            run.value = 3
            showRunState(3)

            if not had_macro_proc:
                continue

            # Generate and send final report AFTER stopping inputs
            try:
                print("Generating final report...")
                from modules.reports.final import FinalReport
                import os
                
                # Create final report object
                finalReportObj = FinalReport()
                sessionStats = finalReportObj.generateFinalReport(setdat, stop_time=time.time())
                
                # Check if report was generated successfully
                if sessionStats and os.path.exists("finalReport.png"):
                    # Format session summary for webhook
                    sessionTime = sessionStats.get("total_session_time", 0)
                    hours = int(sessionTime / 3600)
                    minutes = int((sessionTime % 3600) / 60)
                    seconds = int(sessionTime % 60)
                    if hours > 0:
                        timeStr = f"{hours}h {minutes}m {seconds}s"
                    elif minutes > 0:
                        timeStr = f"{minutes}m {seconds}s"
                    else:
                        timeStr = f"{seconds}s"
                    
                    totalHoney = sessionStats.get("total_honey", 0)
                    avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
                    
                    # Add "Estimated" label if session was less than 1 hour
                    avgLabel = "Est. Avg/Hour" if sessionTime < 3600 else "Avg/Hour"
                    description = f"Runtime: {timeStr}\nTotal Honey: {millify(totalHoney)}\n{avgLabel}: {millify(avgHoneyPerHour)}"
                    
                    # Send final report webhook
                    logger.finalReport("Session Complete", description, "purple", fields=getattr(finalReportObj, "lastEmbedFields", None))
                    print("Final report sent successfully")

                    item_path = getattr(finalReportObj, "lastItemReportPath", None)
                    if item_path and os.path.exists(item_path):
                        logger.itemReport(
                            "Item Monitor",
                            "",
                            "purple",
                            fields=getattr(finalReportObj, "lastItemEmbedFields", None),
                            imagePath=item_path,
                        )
                        print("Item monitor report sent successfully")
                else:
                    print("Failed to generate final report - no data available")
                    
            except Exception as e:
                print(f"Error generating final report: {e}")
                import traceback
                traceback.print_exc()
        elif run.value == 4: #disconnected
            if macroProc and macroProc.is_alive():
                macroProc.kill()
                macroProc.join()
            logger.webhook("","Disconnected", "red", "screen", ping_category="ping_disconnects")
            appManager.closeApp("Roblox")
            keyboardModule.releaseMovement()
            mouse.mouseUp()
            macroProc = startMacroProcess()
            run.value = 2
            showRunState(2)
        # Note: run.value == 6 (paused) is handled in the macro process loop - it waits for resume
        
        # Check for crash (non-zero exitcodes). Log signal name to aid diagnosis.
        if macroProc and not macroProc.is_alive() and macroProc.exitcode:
            extra = ""
            if macroProc.exitcode < 0:
                signum = -macroProc.exitcode
                try:
                    signame = signal.Signals(signum).name
                except ValueError:
                    signame = str(signum)
                extra = f" (terminated by signal {signame})"
            print(f"Macro process exited{extra}")
            logger.webhook("","Macro Crashed{0}".format(extra), "red", "screen", ping_category="ping_critical_errors")
            macroProc.join()
            appManager.openApp("Roblox")
            keyboardModule.releaseMovement()
            mouse.mouseUp()
            # restart macro process
            macroProc = startMacroProcess()
            run.value = 2
            showRunState(2)

        #show every log message queued since the last tick
        while not logQueue.empty():
            logData = logQueue.get()
            recentLogs.append({key: logData[key] for key in ("time", "title", "desc", "color")})
            gui.log(logData["time"], f"{logData['title']}<br>{logData['desc']}", logData["color"])
        # keep only the last 100 entries for the discord bot
        if len(recentLogs) > 100:
            try:
                recentLogs[:] = recentLogs[-100:]
            except Exception:
                pass  # the manager process may be shutting down
        
        #detect if the gui needs to be updated
        if updateGUI.value:
            gui.updateGUI()
            updateGUI.value = 0
        
        if run.value == 2 and time.time() > disconnectCooldownUntil:
            img = adjustImage("./images/menu", "disconnect", screenInfo["display_type"])
            wmx, wmy, wmw, wmh = getWindowSize("roblox roblox")
            if locateImageOnScreen(img, wmx+wmw/3, wmy+wmh/2.8, wmw/2.3, wmh/5, 0.7):
                print("disconnected")
                run.value = 4
                disconnectCooldownUntil = time.time() + 300  # 5 min cooldown
