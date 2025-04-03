mt:
	cd meaning_tree && mvn clean install

run:
	uv run main.py

.PHONY: test
test:
	uv run pytest