"""Design tokens: every theme must be readable (WCAG 2.2 AA contrast) for the pairs the interface actually uses."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSS = os.path.join(ROOT, 'web', 'css', 'tokens.css')
THEMES = ['morning', 'evening', 'navy', 'navynight', 'contrast']
# (foreground, background, minimum ratio, what it is)
PAIRS = [
    ('ink', 'canvas', 4.5, 'text on the page'), ('ink', 'surface', 4.5, 'text on cards'), ('ink', 'surface-2', 4.5, 'text on stripes and inputs'),
    ('ink', 'raised', 4.5, 'text on panels'), ('ink-2', 'surface', 4.5, 'secondary text on cards'), ('ink-2', 'canvas', 4.5, 'secondary text on the page'),
    ('ink-3', 'surface', 3.0, 'placeholders and hints'),
    ('brand-ink', 'brand', 4.5, 'text on brand buttons'), ('brand-soft-ink', 'brand-soft', 4.5, 'text on soft brand chips'),
    ('accent-ink', 'accent', 4.5, 'text on the primary button'), ('accent-soft-ink', 'accent-soft', 4.5, 'text on soft accent chips'),
    ('ok-ink', 'ok-soft', 4.5, 'paid / good chip'), ('warn-ink', 'warn-soft', 4.5, 'due soon chip'), ('bad-ink', 'bad-soft', 4.5, 'overdue chip'),
    ('info-ink', 'info-soft', 4.5, 'info chip'),
    ('sidebar-ink', 'sidebar-bg', 4.5, 'sidebar text'), ('sidebar-ink-2', 'sidebar-bg', 4.5, 'sidebar group titles'),
    ('sidebar-active-ink', 'sidebar-active-bg', 4.5, 'active sidebar item'), ('sidebar-ink', 'sidebar-hover', 4.5, 'hovered sidebar item'),
    ('brand', 'surface', 3.0, 'brand-coloured icons and headings on cards'), ('focus', 'surface', 3.0, 'focus ring'),
    ('ok', 'surface', 3.0, 'status dots'), ('bad', 'surface', 3.0, 'status dots'), ('warn', 'surface', 3.0, 'status dots'),
]


def parse_tokens():
    with open(CSS, encoding='utf-8') as f:
        text = f.read()
    themes = {}
    for m in re.finditer(r"(:root(?:\[data-theme='(\w+)'\])?(?:,\s*:root\[data-theme='(\w+)'\])?)\s*\{(.*?)\n\}", text, re.S):
        names = [n for n in (m.group(2), m.group(3)) if n]
        body = dict(re.findall(r'--([\w-]+):\s*(#[0-9a-fA-F]{6})\b', m.group(4)))
        for n in names:
            themes.setdefault(n, {}).update(body)
    return themes


def lum(hexcolor):
    r, g, b = (int(hexcolor[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def ratio(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class TokenContrastTest(unittest.TestCase):
    def test_every_theme_defines_every_token_used(self):
        themes = parse_tokens()
        for t in THEMES:
            self.assertIn(t, themes, t)
            for fg, bg, _, what in PAIRS:
                self.assertIn(fg, themes[t], f'{t}: --{fg}')
                self.assertIn(bg, themes[t], f'{t}: --{bg}')

    def test_contrast_is_at_least_aa_in_every_theme(self):
        themes = parse_tokens()
        bad = []
        for t in THEMES:
            for fg, bg, need, what in PAIRS:
                r = ratio(themes[t][fg], themes[t][bg])
                if r < need:
                    bad.append(f'{t}: {what} --{fg} on --{bg} = {r:.2f} (needs {need})')
        self.assertEqual(bad, [], '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
