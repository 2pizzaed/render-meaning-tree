output_dir="test/output/questions"
#output_dir="test/output/questions/debug"
mkdir -p "$output_dir"

for f in test/data/task_code/*.py; do
#for f in test/data/task_code/debug/*.py; do
    base=$(basename "$f" .py)
    echo
    echo "----------------------------------------"
    echo "Processing $f -> $output_dir/${base}*.json"
    echo "----------------------------------------"
    echo
    python generator.py "$f" --output-dir "$output_dir"
done
# Useful for debugging:
echo "COMPLETED! Press Enter to close me.";
read -r
