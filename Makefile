PY ?= python3

.PHONY: all l4 roots wasm site hunt tla test test-serial serve clean
all: l4 site hunt test

l4:
	$(PY) tools/l4run.py

# only the roots and their tests (`make l4` checks them too)
roots:
	L4_ROOTS=check $(PY) tools/l4run.py l4/roots/*root.l4

# the calculator's evaluator, from its pinned release, into build/l4wasm/
# (toolchain/fetch-wasm.sh, MMS-776); `make site` fetches it too
wasm:
	toolchain/fetch-wasm.sh

site: wasm
	$(PY) tools/build_site.py

# TLC, the TLA+ model checker, into build/tla2tools.jar (toolchain/fetch-tla.sh)
tla:
	toolchain/fetch-tla.sh

# the analysis backends over every file: lts, explore, verify, prove (z3),
# coverage and TLC (tools/hunt.py, MMS-804); after `make l4`, whose results
# the obligations hunter compares with; tests/test_hunt.py holds the counts
hunt: tla
	$(PY) tools/hunt.py

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
