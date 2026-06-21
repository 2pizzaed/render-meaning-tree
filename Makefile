mt:
	./build_libs.sh mt

tpg:
	./build_libs.sh tpg

run:
	uv run main.py

.PHONY: mt tpg rebuild run test
test:
	uv run pytest
