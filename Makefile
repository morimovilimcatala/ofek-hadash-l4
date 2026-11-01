PY ?= python3

.PHONY: all l4 roots site test test-serial serve clean
all: l4 site test

l4:
	$(PY) tools/l4run.py

# only the roots and their tests (`make l4` checks them too)
roots:
	L4_ROOTS=check $(PY) tools/l4run.py l4/lib/*root.l4

site:
	$(PY) tools/build_site.py

# the suite, a test class per process, as many at once as there are cores
# (MMS-617); test-serial is the same suite in one process
test:
	$(PY) tools/run_tests.py

test-serial:
	$(PY) -m unittest discover -s tests

serve: site
	$(PY) -m http.server -d build/site 8000

clean:
	rm -rf build
