# PaperForge — developer and author tasks
# Usage: make help
PY ?= python3
DEMO := examples/demo-paper

.PHONY: help install install-dev test test-fast demo check score refs draft pdf bundle \
        ingest context clean lint doctor all version

help:  ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## install the package (runtime only)
	$(PY) -m pip install -e .

install-dev:  ## install with figures, docx, structures and test extras
	$(PY) -m pip install -e ".[figures,docx,structures,dev]"

test:  ## run the full test suite (network tests skipped)
	$(PY) -m pytest tests/ -q -m "not network"

test-fast:  ## run the fast subset (chemistry + checks)
	$(PY) -m pytest tests/test_chem.py tests/test_checks.py -q

demo:  ## rebuild the demo project from scratch
	cd $(DEMO) && $(PY) build_demo.py

check:  ## check the demo manuscript
	$(PY) -m paperforge check $(DEMO)

score:  ## print the readiness score as JSON
	$(PY) -m paperforge score $(DEMO) --json

refs:  ## verify every DOI in the demo project
	$(PY) -m paperforge refs verify $(DEMO)

draft:  ## render markdown, LaTeX, DOCX, cover letter
	$(PY) -m paperforge draft $(DEMO) --format all --cover-letter

pdf: draft  ## compile the LaTeX into PDF (needs tectonic)
	cd $(DEMO)/build && tectonic -X compile manuscript.tex

bundle:  ## build the submission zip (refuses on blockers)
	$(PY) -m paperforge bundle $(DEMO) --strict

ingest:  ## turn a folder into a project: make ingest SRC=folder OUT=project
	$(PY) -m paperforge ingest "$(SRC)" --out "$(OUT)"

context:  ## dump the grounded evidence pack for an LLM
	$(PY) -m paperforge context $(DEMO)

doctor:  ## environment self-test
	$(PY) -m paperforge doctor

version:  ## print the version
	$(PY) -m paperforge --version

all: test demo check refs draft  ## full verification pass

clean:  ## remove build artefacts
	rm -rf $(DEMO)/build .pytest_cache **/__pycache__ paperforge/__pycache__
