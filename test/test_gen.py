import json
import unittest
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.ast_analyzer import ASTNodeAnalyzer
from src.cfg import ASTNodeWrapper, CFGBuilder
from src.cfg.abstractions import InterruptionType, SituationState, load_constructs
from src.cfg.cfg import idgen
from src.cfg.cfg_graphviz import visualize_cfg_graphviz
from src.cfg.loqi_exporter import LoqiExporter
from src.cfg.reachability import determine_all_paths_between_opaque_nodes
from src.cfg.trace_builder import TraceScenarioConfig, generate_trace_variants
from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_dict, to_tokens
from src.qgen_utils import build_answer_objects_from_cfg


class TestComplexProblemBuild(unittest.TestCase):
    def test_generate(self):
        current_dir = Path(__file__).parent

        # Путь к папке с входными данными и выходной папке
        task_data_path = current_dir / "data" / "task_code"
        genout_path = current_dir / "output" / "code_snippets"
        genout_path.mkdir(parents=True, exist_ok=True)

        # Загружаем конструкции
        constructs = load_constructs("constructs.yml")

        files = task_data_path.iterdir()
        # files = [task_data_path / "2_functions.py"]

        # Перебираем все файлы в task_data
        for file in files:
            # Начинаем нумерацию узлов с начала для каждого файла, таким образом, порядок обработки файлов не влияет на id узлов.
            idgen.reset()
            # if file.stem not in ('21', ):
            #     continue

            print("Processing file:", file.name)

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

            source_map: dict[str, Any] | None = convert(
                code, language, language, source_map=True
            ) # type: ignore

            if source_map is None:
                self.fail(f"Failed to convert code for {file.name}")

            map_json_path = genout_path / f"{file.stem}_map.json"
            with open(map_json_path, "w", encoding="utf-8") as f:
                json.dump(source_map, f, indent=2, ensure_ascii=False)
            ast_json_path = genout_path / f"{file.stem}.json"
            ast_json = source_map.get("origin", {}).get("root_node")
            with open(ast_json_path, "w", encoding="utf-8") as f:
                json.dump(ast_json, f, indent=2, ensure_ascii=False)

            ast = ASTNodeAnalyzer(ast_json, source_map)

            tokens = to_tokens(language, source_map["source_code"])

            if tokens is None:
                self.fail(f"Failed to tokenize code for {file.name}")

            tok_json_path = genout_path / f"{file.stem}_tokens.json"
            with open(tok_json_path, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=2, ensure_ascii=False)

            htmlgen = CodeHighlightGenerator()
            htmlgen.debug = True
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
                    interruption_state=InterruptionType.NO_INTERRUPTION,
                )
            )
            exporter.set_var("STATE", situation)

            # Конфигурации трасс: сейчас используем один сценарий по умолчанию,
            # но оставляем возможность добавить несколько.
            scenarios = [
                TraceScenarioConfig(name="default"),
                # TraceScenarioConfig(name="alt", condition_sequences={...}),
            ]

            trace_results = generate_trace_variants(cfg, scenarios)

            # Пока экспортируем только первую сгенерированную трассу,
            # остальные сценарии можно будет добавить при необходимости.
            main_trace = trace_results[0].trace_acts
            self.assertTrue(len(main_trace))
            # Используем add_trace вместо add_object, чтобы установить связи directlyBeforeOf
            exporter.add_trace(main_trace)

            # Добавляем пути между узлами
            paths = determine_all_paths_between_opaque_nodes(cfg)
            if paths:
                exporter.add_paths(paths)

            exporter.export_cfg(cfg, str(loqi_path))

            # Визуализируем CFG в PNG (режим с рёбрами)
            png_path = (genout_path / f"{file.stem}-edge.png").absolute()
            visualize_cfg_graphviz(cfg, str(png_path))

            # Визуализируем CFG в PNG (режим с путями)
            png_pathinfo_path = (genout_path / f"{file.stem}-pathinfo.png").absolute()
            visualize_cfg_graphviz(cfg, str(png_pathinfo_path), paths_instead_of_edges=True)

            answ = build_answer_objects_from_cfg(cfg,
                                                 lines_data,
                                                 include_end_button=False, ast=ast)
            answ_clear = {}
            for a in answ:
                answ_clear[a["answerId"]] = a["domainInfo"]

            soup = BeautifulSoup(html, "html.parser")
            code_block = soup.select_one("#answer_objects")
            if code_block:
                code_block.string = json.dumps(answ_clear, indent=4)
            html = str(soup)

            html_path = (genout_path / f"{file.stem}.html").absolute()
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

            print(f"Processed {file.name}:")
            print(f"  AST JSON: {ast_json_path}")
            print(f"  LOQI: {loqi_path}")
            print(f"  PNG (edges): {png_path}")
            print(f"  PNG (paths): {png_pathinfo_path}")
