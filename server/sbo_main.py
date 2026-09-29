"""Entry point of the installed program (SBO.exe, built by tools/build_windows.py).

  SBO.exe                 start the program and open it in a window
  SBO.exe --background    start the program without opening the browser (used when Windows starts)
  SBO.exe tool <command>  maintenance tools of server/core/nodectl.py (status, verify, rebuild, reset-admin,
                          export-authority <file>, import-authority <file>) - run it from a command window

The installed program keeps its data outside the program folder, in %ProgramData%\\<Brand> (config.json, data,
backups), so an update replaces only the program and never touches the data.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'core'))

FOLDER = 'SelfBusinessOS'   # folder name under ProgramData; the visible brand name is a setting, this is only a technical folder


def home_dir():
    """Where the installed program keeps config, data and backups."""
    base = os.environ.get('ProgramData') or os.environ.get('ALLUSERSPROFILE') or os.path.expanduser('~')
    return os.path.join(base, FOLDER)


def main(argv):
    if sys.stdout is None:  # started without a console window
        sys.stdout = open(os.devnull, 'w')
    if sys.stderr is None:
        sys.stderr = sys.stdout
    if not os.environ.get('SBO_HOME'):
        os.environ['SBO_HOME'] = home_dir()
    os.makedirs(os.environ['SBO_HOME'], exist_ok=True)
    if argv[:1] == ['tool']:
        import nodectl
        return nodectl.main(argv[1:])
    import app
    app.main(background='--background' in argv)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
