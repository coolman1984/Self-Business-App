"""Opens the program's address in its own plain window ("app mode") when Microsoft Edge or Google Chrome is installed, so it
feels like a normal program without tabs or address bar; otherwise in the default browser. Nothing here touches data."""
import os
import subprocess
import sys
import webbrowser

WINDOWS_BROWSERS = [
    (r'Microsoft\Edge\Application\msedge.exe', ('ProgramFiles(x86)', 'ProgramFiles', 'LocalAppData')),
    (r'Google\Chrome\Application\chrome.exe', ('ProgramFiles', 'ProgramFiles(x86)', 'LocalAppData')),
]


def app_browser(env=None, exists=os.path.isfile, platform=None):
    """Full path of an installed Edge/Chrome, or None (also None on other systems than Windows)."""
    env = os.environ if env is None else env
    if (platform or sys.platform) != 'win32':
        return None
    for rel, roots in WINDOWS_BROWSERS:
        for root in roots:
            base = env.get(root)
            if base and exists(os.path.join(base, rel)):
                return os.path.join(base, rel)
    return None


def open_app(url, app_mode=True, popen=subprocess.Popen, opener=webbrowser.open):
    """Returns 'app' when opened in an app window, 'browser' otherwise."""
    exe = app_browser() if app_mode else None
    if exe:
        try:
            popen([exe, f'--app={url}', '--window-size=1360,860'], close_fds=True)
            return 'app'
        except OSError:
            pass
    opener(url)
    return 'browser'
