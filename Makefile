PYTEST_XDIST_WORKERS ?= 4

.PHONY: mt tpg rebuild run test test-parallel test-serial

mt:
	./build_libs.sh mt

tpg:
	./build_libs.sh tpg

rebuild: mt tpg

run:
	uv run main.py

test: test-parallel test-serial

test-parallel:
	uv run pytest -n $(PYTEST_XDIST_WORKERS) --dist=loadgroup -m "not serial"

test-serial:
	uv run pytest -m serial
