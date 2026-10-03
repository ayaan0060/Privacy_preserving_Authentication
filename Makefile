.PHONY: all reproduce verify experiments macros figures tables paper test clean

PYTHON = .venv/bin/python3
TECTONIC = tectonic

all: reproduce verify

reproduce:
	$(PYTHON) scripts/run_all_experiments.py
	$(PYTHON) scripts/make_macros.py
	$(PYTHON) scripts/make_tables.py
	$(PYTHON) scripts/make_figures.py

verify:
	$(PYTHON) scripts/lint_paper.py
	$(PYTHON) -m unittest discover tests
	$(TECTONIC) paper.tex
	$(TECTONIC) Research.tex

experiments:
	$(PYTHON) scripts/run_all_experiments.py

macros:
	$(PYTHON) scripts/make_macros.py

figures:
	$(PYTHON) scripts/make_figures.py

tables:
	$(PYTHON) scripts/make_tables.py

test:
	$(PYTHON) -m unittest discover tests

paper: tables figures macros
	$(TECTONIC) paper.tex
	$(TECTONIC) Research.tex

clean:
	rm -f *.aux *.bbl *.blg *.log *.out *.toc *.synctex.gz *.xdv
