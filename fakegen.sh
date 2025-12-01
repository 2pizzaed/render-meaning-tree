mkdir -p test/output/questions/
for f in test/data/task_code/*.py; do
    base=$(basename "$f" .py)
    echo
    echo "----------------------------------------"
    echo "Processing $f -> test/output/questions/${base}.json"
    echo "----------------------------------------"
    echo
    python generator.py "$f" > "test/output/questions/${base}.json"
done
# Useful for debugging:
echo "COMPLETED! Press Enter to close me.";
read -r
