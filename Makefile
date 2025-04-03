mt:
	cd meaning_tree && mvn clean install

run:
	uv run main.py

test:
	uv run pytest