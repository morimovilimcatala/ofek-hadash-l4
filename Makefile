PY ?= python3

.PHONY: all l4 roots site test serve clean
all: l4 site test

l4:
	$(PY) tools/l4run.py

# the roots and their tests, on demand (tools/l4run.py roots_checked)
roots:
	L4_ROOTS=check $(PY) tools/l4run.py l4/lib/*root.l4

site:
	$(PY) tools/build_site.py

test:
	$(PY) -m unittest discover -s tests

serve: site
	$(PY) -m http.server -d build/site 8000

clean:
	rm -rf build
