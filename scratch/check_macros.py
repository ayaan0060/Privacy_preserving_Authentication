import re
from pathlib import Path

tex = Path('paper.tex').read_text()
macros_tex = Path('results/final/macros.tex').read_text()

defs = set(re.findall(r'\\newcommand\{\\([a-zA-Z0-9]+)\}', macros_tex))
used = set(re.findall(r'\\([A-Z][a-zA-Z0-9]+)\b', tex))

standard = {
    'textbf', 'textit', 'text', 'section', 'subsection', 'subsubsection',
    'caption', 'label', 'ref', 'cite', 'begin', 'end', 'input', 'resizebox',
    'centering', 'toprule', 'midrule', 'bottomrule', 'cmidrule', 'multicolumn',
    'footnotesize', 'scriptsize', 'Huge', 'Large', 'IEEEtitleabstractindextext',
    'IEEEpeerreviewmaketitle', 'IEEEoverridecommandlockouts', 'IEEEkeywords',
    'PARstart', 'subfloat', 'includegraphics', 'hfill', 'vspace', 'hspace',
    'noindent', 'mathcal', 'mathbf', 'mathbb', 'mathrm', 'textsf', 'bm',
    'Prob', 'DeclareMathOperator', 'Package', 'documentclass', 'usepackage',
    'title', 'author', 'thanks', 'left', 'right', 'times', 'pm', 'le', 'ge',
    'approx', 'sim', 'langle', 'rangle', 'Vert', 'vert', 'dots', 'cdots',
    'sum', 'prod', 'min', 'max', 'arg', 'forall', 'exists', 'in', 'subset',
    'cap', 'cup', 'neq', 'equiv', 'dagger', 'ddagger', 'Table', 'Figure', 'Section'
}

unknown = [u for u in used if u not in defs and u not in standard]
print('Unknown macros in paper.tex:', unknown)
