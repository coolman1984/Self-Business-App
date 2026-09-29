"""Program entry for development and tests:  python server/app.py   (settings from SBO_CONFIG or config.json next to it).
The installed program uses server/sbo_main.py, which sets SBO_HOME to the ProgramData folder first."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'core'))

import bootstrap  # noqa: E402
import httpd  # noqa: E402


def main(background=False):
    home = os.environ.get('SBO_HOME') or os.path.dirname(HERE)
    bootstrap.register_domains()
    app = httpd.App(home, os.environ.get('SBO_CONFIG') or os.path.join(home, 'config.json'), root=os.path.dirname(HERE))
    for name in filter(None, os.environ.get('SBO_ENTITY_MODULES', '').split(',')):
        mod = __import__(name.strip())
        if hasattr(mod, 'routes'):
            mod.routes(app)
    httpd.run(app, background)


if __name__ == '__main__':
    main('--background' in sys.argv)
