"""Example Mod - the smallest mod the Pipeline Kit's self-test can carry through every stage.

A Mod Organizer 2 Python plugin with one toolbar button that shows a hello dialog. Chosen because it needs no
compiler: the pipeline's mechanics (identity, issued numbers, changelog, package gate, earned "working", finalize
gate) are the same for a one-file plugin as for a 40-file SKSE DLL.

The version below is a LOCATION the version gate owns: `version-gate.ps1 -Action register` discovers it,
`-Action bump` writes it, and `-Action gate` refuses any package whose files disagree with it. Never type it.
"""
__version__ = "1.0.0"

try:
    import mobase  # noqa: F401  (present only inside Mod Organizer 2)
    from PyQt6.QtWidgets import QMessageBox
    from PyQt6.QtGui import QIcon
except ImportError:  # the self-test imports nothing; this file only has to exist and carry its version
    mobase = None


class ExampleMod(mobase.IPluginTool if mobase else object):
    def __init__(self):
        super().__init__()
        self._organizer = None

    def init(self, organizer):
        self._organizer = organizer
        return True

    def name(self):
        return "Example Mod"

    def author(self):
        return "you"

    def description(self):
        return "The Pipeline Kit's example: one button, one dialog."

    def version(self):
        a, b, c = (int(x) for x in __version__.split("."))
        return mobase.VersionInfo(a, b, c, mobase.ReleaseType.FINAL)

    def settings(self):
        return []

    def displayName(self):
        return "Example Mod"

    def tooltip(self):
        return "Says hello."

    def icon(self):
        return QIcon()

    def display(self):
        QMessageBox.information(None, "Example Mod", f"Hello from Example Mod {__version__}.")


def createPlugin():
    return ExampleMod()


# --- fault handling (a standing rule of the pipeline: every MO2 plugin logs and arms faulthandler) ------------------
# The package gate's rule mo2-plugin-arms-faulthandler REQUIRES this block in any plugin that imports mobase: when MO2
# dies inside C++ with a Python slot on the stack, the minidump names only modules; faulthandler writes the Python
# frames of every thread to plugins\data\faults.log first, so the log names the plugin and the line.
def _arm_faulthandler():
    try:
        import faulthandler
        import os
        import time
        if faulthandler.is_enabled():
            return
        here = os.path.abspath(__file__)
        while os.path.basename(here).lower() != "plugins":
            parent = os.path.dirname(here)
            if parent == here:
                return
            here = parent
        path = os.path.join(here, "data", "faults.log")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fh = open(path, "a", encoding="utf-8")
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + " faulthandler armed by " + os.path.basename(__file__) + chr(10))
        fh.flush()
        globals()["_FAULT_LOG_HANDLE"] = fh          # kept open for the life of the process
        faulthandler.enable(file=fh, all_threads=True)
    except Exception:  # noqa: BLE001
        pass


_arm_faulthandler()
