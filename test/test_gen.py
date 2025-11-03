import json
import unittest
from pathlib import Path
from typing import Any

from src.cfg import ASTNodeWrapper, CFGBuilder
from src.cfg.abstractions import InterruptionType, SituationState, load_constructs
from src.cfg.cfg_graphviz import visualize_cfg_graphviz
from src.cfg.loqi_exporter import LoqiExporter
from src.cfg.reachability import determine_all_paths_between_opaque_nodes
from src.cfg.trace_builder import all_interactions, build_trace_act
from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_dict, to_tokens


class TestComplexProblemBuild(unittest.TestCase):
    def test_generate(self):
        current_dir = Path(__file__).parent

        # Путь к папке с входными данными и выходной папке
        task_data_path = current_dir / "task_code"
        genout_path = current_dir / "genout"
        genout_path.mkdir(exist_ok=True)

        # Перебираем все файлы в task_data
        for file in task_data_path.iterdir():
            language = file.suffix.lstrip(".")

            if language == "py":
                language = "python"
            elif language == "cpp":
                language = "c++"
            elif language == "java":
                language = "java"

            with open(file, encoding="utf-8") as f:
                code = f.read()

            ast_json = to_dict(language, code)
            if not ast_json:
                self.fail(f"Failed to generate AST for {file.name}")

            # Сохраняем AST JSON в genout
            ast_json_path = genout_path / f"{file.stem}.json"
            with open(ast_json_path, "w", encoding="utf-8") as f:
                json.dump(ast_json, f, indent=2)

            source_map: dict[str, Any] | None = convert(
                code, language, language, source_map=True
            ) # type: ignore

            if source_map is None:
                self.fail(f"Failed to convert code for {file.name}")

            tokens = to_tokens(language, source_map["source_code"])

            if tokens is None:
                self.fail(f"Failed to tokenize code for {file.name}")

            htmlgen = CodeHighlightGenerator()
            lines_data = htmlgen.prepare_interactive_data(
                source_map,
                tokens,
            )
            html = htmlgen.generate_html(
                lines_data,
                source_map,
            )

            # Создаём ASTNodeWrapper
            program_root = ASTNodeWrapper(ast_node=ast_json)

            # Загружаем конструкции
            constructs = load_constructs("constructs.yml")
            b = CFGBuilder(constructs)

            # Генерируем CFG
            cfg = b.make_cfg_for_ast(program_root)

            if cfg is None:
                self.fail(f"Failed to build CFG for {file.name}")

            # Оптимизируем CFG
            cfg.optimize()

            # Экспортируем в LOQI
            exporter = LoqiExporter()
            loqi_path = (genout_path / f"{file.stem}.loqi").absolute()

            exporter.add_object(
                situation := SituationState(
                    interruption_state=InterruptionType.NONE,
                )
            )
            exporter.set_var("STATE", situation)

            trace_acts = [
                build_trace_act(cfg, interaction) for interaction in all_interactions(lines_data)
            ]
            for trace_act in trace_acts:
                exporter.add_object(trace_act)

            # Добавляем пути между узлами
            paths = determine_all_paths_between_opaque_nodes(cfg)
            if paths:
                exporter.add_paths(paths)

            exporter.export_cfg(cfg, str(loqi_path))

            # Визуализируем CFG в PNG
            png_path = (genout_path / f"{file.stem}.png").absolute()
            visualize_cfg_graphviz(cfg, str(png_path))

            html_path = (genout_path / f"{file.stem}.html").absolute()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            print(f"Processed {file.name}:")
            print(f"  AST JSON: {ast_json_path}")
            print(f"  LOQI: {loqi_path}")
            print(f"  PNG: {png_path}")
