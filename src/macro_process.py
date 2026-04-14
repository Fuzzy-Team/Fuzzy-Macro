import traceback


def macro_process_entry(status, logQueue, updateGUI, run, skipTask, presence=None):
    print("\n--- Fuzzy Macro macro subprocess start ---", flush=True)
    try:
        from main import macro

        return macro(status, logQueue, updateGUI, run, skipTask, presence)
    except BaseException:
        print("\n--- Fuzzy Macro macro subprocess crash ---", flush=True)
        traceback.print_exc()
        raise
