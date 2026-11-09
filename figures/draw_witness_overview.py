"""Render the C01 comparison and its complete four-value domain."""
from pathlib import Path
from visual_grammar import BLUE, GRID, GREEN, RED, WARM, Diagram


def draw(out):
    d = Diagram(h=102)
    d.doc(28, 70)
    d.arrow((43, 70), (68, 70), c=BLUE)
    d.text(81, 81, 'C01: x = 3', 10, BLUE, 'left', True)
    d.text(81, 59, 'Old: overflow', 9.5, RED, 'left')
    d.text(81, 37, 'New: returns 3', 9.5, BLUE, 'left')
    d.text(208, 85, 'Declared domain (y unused)', 10, ha='left', bold=True)
    d.rect(370, 36, 46, 17, WARM)
    d.rect(370, 17, 46, 17, GREEN)
    d.line((207, 57), (416, 57), c=GRID)
    for y, label, values in (
        (66, 'Input', ('0', '1', '2', '3')),
        (45, 'Old', ('1', '2', '3', 'fault')),
        (25, 'New', ('1', '2', '3', '3')),
    ):
        d.text(208, y, label, 9.5, ha='left', bold=y == 66)
        for x, value in zip((263, 306, 349, 393), values):
            if x == 393 and y < 66:
                d.text(x, y, value, 9.5, RED if y == 45 else BLUE, bold=True)
            else:
                d.text(x, y, value, 9.5, bold=y == 66)
    d.finish(out)


if __name__ == '__main__':
    draw(Path(__file__).resolve().parent / 'illustrations' / 'evidence-ladder.pdf')
