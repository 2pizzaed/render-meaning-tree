mkdir -p test/output/questions/
for f in test/data/task_code/*.py; do
    base=$(basename "$f" .py)
    python generator.py "$f" > "test/output/questions/${base}.json"
done