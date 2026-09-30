"""Opening the program in its own window: picks Edge, then Chrome, only on Windows; never fails when none exists."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server', 'core'))
import launcher  # noqa: E402


class Launcher(unittest.TestCase):
    ENV = {'ProgramFiles(x86)': r'C:\pf86', 'ProgramFiles': r'C:\pf', 'LocalAppData': r'C:\local'}

    def test_edge_is_preferred_when_present(self):
        both = lambda p: True  # noqa: E731
        self.assertIn('msedge.exe', launcher.app_browser(self.ENV, both, 'win32'))

    def test_chrome_when_no_edge(self):
        only_chrome = lambda p: 'chrome.exe' in p  # noqa: E731
        self.assertIn('chrome.exe', launcher.app_browser(self.ENV, only_chrome, 'win32'))

    def test_none_when_nothing_installed_or_not_windows(self):
        self.assertIsNone(launcher.app_browser(self.ENV, lambda p: False, 'win32'))
        self.assertIsNone(launcher.app_browser(self.ENV, lambda p: True, 'linux'))

    def test_falls_back_to_the_default_browser(self):
        opened = []
        self.assertEqual(launcher.open_app('http://localhost:1/', True, popen=None, opener=opened.append), 'browser')
        self.assertEqual(opened, ['http://localhost:1/'])

    def test_app_mode_off_uses_the_default_browser(self):
        opened = []
        self.assertEqual(launcher.open_app('http://x/', False, popen=None, opener=opened.append), 'browser')

    def test_a_failing_start_falls_back(self):
        orig = launcher.app_browser
        launcher.app_browser = lambda *a, **k: r'C:\edge.exe'
        try:
            def boom(*a, **k):
                raise OSError('no')
            opened = []
            self.assertEqual(launcher.open_app('http://x/', True, popen=boom, opener=opened.append), 'browser')
            self.assertEqual(opened, ['http://x/'])
        finally:
            launcher.app_browser = orig


if __name__ == '__main__':
    unittest.main()
