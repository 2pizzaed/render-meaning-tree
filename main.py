import argparse
import json

from src.ast_managers import prepare_code
from src.cfg_tools import cfg
from src.coderenderer.html import prepare_html_context, render_static_html
from src.meaning_tree import to_dict


def save_as_html(code: str, language: str, output_file: str = "output.html"):
    manager = prepare_code(code, language)
    context = prepare_html_context(manager)
    render_static_html(context, output_path=output_file, snippet_only=True)


def save_cfg(node, output_file="cfg.png"):
    graph = cfg.generate_cfg(node)
    return cfg.visualize(output_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process code into meaning tree and generate visualizations"
    )
    parser.add_argument("--file", "-f", help="Source file to process")
    parser.add_argument("--code", "-c", help="Code string to process")
    parser.add_argument("--cfg", "-g", action="store_true", help="Generate control flow graph")
    parser.add_argument(
        "--output", "-o", default="result", help="Output filename (without extension)"
    )
    parser.add_argument(
        "--analyze", "-a", action="store_true", help="Print CFG analysis information"
    )

    args = parser.parse_args()

    # file_path = args.file
    N = 10
    file_path = f"test/data/examples/code_example{N}.py"

    if file_path:
        with open(file_path) as f:
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
        with open(f"test/data/ast/ast{N}.json", "w") as f:
            json.dump(ast, f, indent=2)

    html_output = f"{args.output}.html"
    save_as_html(code, "python", output_file=html_output)
    print(f"HTML output saved to {html_output}")

    if 0 and args.cfg:
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

    # from src.serializers.compprehension_serializer import serialize
    # from pprint import pprint
    # pprint(serialize(ast))
