PY ?= python3

.PHONY: all l4 site test serve clean
all: l4 site test

l4:
	$(PY) tools/l4run.py

site:
	$(PY) tools/build_site.py

test:
	$(PY) -m unittest discover -s tests

serve: site
	$(PY) -m http.server -d build/site 8000

clean:
	rm -rf build
