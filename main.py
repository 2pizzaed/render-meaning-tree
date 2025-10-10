import json

from src.meaning_tree import to_dict
from src.cfg_tools import cfg
import argparse


def save_as_html(node):
    # from java_renderer import program_entry_point
    from python_renderer import program_entry_point

    html = program_entry_point(node)
    with open("result.html", "w", encoding='utf8') as f:
        f.write(html)


def save_cfg(node, output_file="cfg.png"):
    graph = cfg.generate_cfg(node)
    return cfg.visualize(output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process code into meaning tree and generate visualizations")
    parser.add_argument("--file", "-f", help="Java source file to process")
    parser.add_argument("--code", "-c", help="Java code string to process")
    parser.add_argument("--cfg", "-g", action="store_true", help="Generate control flow graph")
    parser.add_argument("--output", "-o", default="result", help="Output filename (without extension)")
    parser.add_argument("--analyze", "-a", action="store_true", help="Print CFG analysis information")

    args = parser.parse_args()

    if args.file:
        with open(args.file, "r") as f:
            code = f.read()
    elif args.code:
        code = args.code
    else:
        parser.print_help()
        exit(1)

    # ast = to_dict("java", code)
    # ast = to_dict("c++", code)
    ast = to_dict("python", code)

    if not ast:
        print("Failed to parse the code")
        exit(1)

    if 1:
        # save json
        with open("test/ast4.json", "w") as f:
           json.dump(ast, f, indent=2)

    html_output = f"{args.output}.html"
    save_as_html(ast)
    print(f"HTML output saved to {html_output}")

    if args.cfg:
        cfg_output = f"{args.output}_cfg.png"
        cfg_graph = cfg.generate_cfg(ast)
        cfg.visualize(cfg_output)
        print(f"Control flow graph saved to {cfg_output}")

        if args.analyze:
            print("\nCFG Analysis:")
            print(f"- Number of basic blocks: {len(cfg.blocks)}")
            print(f"- Reducible: {cfg.is_reducible()}")
            print(f"- Loop headers: {len(cfg.loop_headers)}")
            print(f"- Loop connectedness: {cfg.get_loop_connectedness()}")
            print(f"- Back edges: {len(cfg.back_edges)}")
            print(f"- Critical edges: {len(cfg.critical_edges)}")
            print(f"- Impossible edges: {len(cfg.impossible_edges)}")

    from src.serializers.compprehension_serializer import serialize
    from pprint import pprint
    pprint(serialize(ast))
    
    
    
