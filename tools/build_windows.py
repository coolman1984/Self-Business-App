"""Builds the Windows installer SBO-Setup-<version>.exe (run on Windows; GitHub does it automatically, see
.github/workflows/build.yml).

Steps: pack the web pages into server/_assets.py, draw the icon, compile the program into SBO.exe with Nuitka
(Python translated to C, no readable source files), then wrap it in the Inno Setup installer.

    python tools/build_windows.py            needs: pip install nuitka ordered-set zstandard, and Inno Setup 6
"""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, 'build')
CORE = os.path.join(ROOT, 'server', 'core')
sys.path.insert(0, CORE)
from version import COPYRIGHT, DEVELOPER, PRODUCT, VERSION  # noqa: E402


def run(cmd, env=None):
    print('>', ' '.join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT, env=env)


def iscc():
    for p in [shutil.which('iscc'), r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe', r'C:\Program Files\Inno Setup 6\ISCC.exe']:
        if p and os.path.exists(p):
            return p
    sys.exit('Inno Setup 6 (ISCC.exe) was not found.')


def compile_program(v4):
    # the engine modules live in server/core and are imported by plain name: Nuitka must see that folder on its search path
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([CORE, os.path.join(ROOT, 'server'), os.environ.get('PYTHONPATH', '')]))
    modules = [f[:-3] for f in os.listdir(CORE) if f.endswith('.py')]
    run([sys.executable, '-m', 'nuitka', '--standalone', '--assume-yes-for-downloads', '--windows-console-mode=attach',
         f'--output-dir={BUILD}', '--output-filename=SBO.exe', f'--windows-icon-from-ico={os.path.join(BUILD, "sbo.ico")}',
         f'--company-name={DEVELOPER}', f'--product-name={PRODUCT}', f'--file-description={PRODUCT}', f'--file-version={v4}',
         f'--product-version={v4}', f'--copyright={COPYRIGHT}', *[f'--include-module={m}' for m in modules], '--include-module=_assets', '--include-package=business',
         '--nofollow-import-to=tkinter,unittest,pydoc,test', os.path.join('server', 'sbo_main.py')], env=env)


def main():
    os.makedirs(BUILD, exist_ok=True)
    assets = os.path.join(ROOT, 'server', '_assets.py')
    run([sys.executable, 'tools/make_assets.py', assets])
    run([sys.executable, 'tools/make_icon.py', os.path.join(BUILD, 'sbo.ico')])
    v4 = '.'.join((VERSION.split('.') + ['0', '0', '0'])[:4])
    try:
        compile_program(v4)
    finally:  # never leave the packed pages next to the source: a development run would serve them instead of web/
        if os.path.exists(assets):
            os.remove(assets)
    dist = os.path.join(BUILD, 'sbo_main.dist')
    assert os.path.exists(os.path.join(dist, 'SBO.exe')), 'SBO.exe was not built'
    leaks = [p for p in glob.glob(os.path.join(dist, '**', '*.py'), recursive=True)]
    assert not leaks, f'source files in the program folder: {leaks}'
    run([iscc(), f'/DAppVersion={VERSION}', f'/DAppPublisher={DEVELOPER}', f'/DAppCopyright={COPYRIGHT}', os.path.join('installer', 'sbo.iss')])
    print('Done:', glob.glob(os.path.join(ROOT, 'dist', f'SBO-Setup-{VERSION}.exe')))


if __name__ == '__main__':
    main()
