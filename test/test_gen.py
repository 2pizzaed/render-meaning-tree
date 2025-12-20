import json
import sys
import unittest
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.ast_analyzer import ASTNodeAnalyzer
from src.cfg import ASTNodeWrapper, CFGBuilder
from src.cfg.abstractions import InterruptionType, SituationState, load_constructs
from src.cfg.cfg import idgen
from src.cfg.cfg_graphviz import visualize_cfg_graphviz
from src.cfg.condition_exporter import (
    DEFAULT_SEED,
    export_condition_decisions,
    export_trace_acts,
    load_scenarios_from_file,
    plan_to_scenario_config,
)
from src.cfg.loqi_exporter import LoqiExporter
from src.cfg.reachability import determine_all_paths_between_opaque_nodes
from src.cfg.trace_builder import TraceScenarioConfig, generate_trace_variants
from src.code_renderer import CodeHighlightGenerator
from src.meaning_tree import convert, to_dict, to_tokens
from src.qgen_utils import build_answer_objects_from_cfg
from src.runtime import (
    execute_with_trace,
    enrich_trace_with_runtime,
    export_scenario_from_trace,
    build_line_to_ast_id_for_conditions,
)

INJECT_RUNTIME_VALUES = False

SAVE_DEBUG_GRAPHS_PHG = False

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
            ###
            if file.stem not in (
                file.stem,  # NO FILTERING
                # '1_onefunc_while',
                # '3_recursion',
                # '5_inf_recursion',
                # '5_inf_recursion2',
                '8_factorial',
                # '9_expr_class',
                # '11_fill',
                # '12_dirscan',
            ):
                continue
            ###

            print("Processing file:", file.name)

            language = file.suffix.lstrip(".")

            if language == "py":
                language = "python"
            elif language == "cpp":
                language = "c++"
            elif language == "java":
                language = "java"
            else:
                continue

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
            program_root = ASTNodeWrapper(ast_node=ast_json, _astnodeanalyzer=ast)

            b = CFGBuilder(constructs)

            # Генерируем CFG
            cfg = b.make_cfg_for_ast(program_root)

            if cfg is None:
                self.fail(f"Failed to build CFG for {file.name}")

            # Оптимизируем CFG
            cfg.optimize()

            # Загружаем планы сценариев из файла (если существует)
            scenarios_file = current_dir / "data" / "task_code" / f"{file.stem}_scenarios.json"
            if scenarios_file.exists():
                scenario_plans = load_scenarios_from_file(scenarios_file)
                scenarios = [
                    plan_to_scenario_config(plan, cfg) for plan in scenario_plans
                ]
            else:
                # Используем сценарий по умолчанию
                scenarios = [
                    TraceScenarioConfig(name="default", seed=DEFAULT_SEED),
                ]

            trace_results = generate_trace_variants(cfg, scenarios)
            # self.assertTrue(len(trace_results) > 0)
            if not trace_results:
                print(f"Failed to generate traces for {file.name}", file=sys.stderr)
                continue

            # Выполняем код с runtime трассировкой (только для Python)
            runtime_trace = None
            generated_scenario = None
            if INJECT_RUNTIME_VALUES and language == "python":
                try:
                    # Строим маппинг line -> ast_id для условий
                    line_to_ast_id = build_line_to_ast_id_for_conditions(ast)
                    
                    # Выполняем код с захватом условий
                    runtime_trace = execute_with_trace(
                        code,
                        filename=str(file),
                        track_conditions=True,
                        line_to_ast_id=line_to_ast_id,
                    )
                    
                    if runtime_trace.exception:
                        print(f"  Warning: Runtime execution failed: {runtime_trace.exception}")
                        # Всё равно сохраняем сценарий, если есть условия
                    
                    # Генерируем сценарий из runtime трассы
                    # Сохраняем сценарий, если есть любые события (не только условия)
                    if runtime_trace.events:
                        generated_scenario = export_scenario_from_trace(
                            runtime_trace,
                            scenario_name="default",
                            ast_analyzer=ast
                        )
                        
                        # Сохраняем сценарий в файл
                        scenario_output_path = genout_path / f"{file.stem}_scenarios.json"
                        with open(scenario_output_path, "w", encoding="utf-8") as f:
                            json.dump(generated_scenario, f, indent=2, ensure_ascii=False)
                        
                        events_count = len(generated_scenario.get("events", []))
                        conditions_count = len(runtime_trace.condition_evaluations)
                        calls_count = len(runtime_trace.function_calls)
                        returns_count = len(runtime_trace.function_returns)
                        print(f"  Generated scenario: {scenario_output_path.name} "
                              f"({events_count} events: {conditions_count} conditions, "
                              f"{calls_count} calls, {returns_count} returns)")
                    
                except Exception as e:
                    print(f"  Warning: Could not execute code for runtime tracing: {e}")

            # Добавляем пути между узлами (одинаковые для всех сценариев)
            paths = determine_all_paths_between_opaque_nodes(cfg)

            # Экспортируем каждый сценарий отдельно
            exported_files = []
            for result in trace_results:
                scenario_name = result.scenario.name
                main_trace = result.trace_acts
                self.assertTrue(len(main_trace))

                # Обогащаем трассу runtime информацией
                if runtime_trace is not None:
                    enrich_trace_with_runtime(main_trace, runtime_trace, ast)

                # Создаём отдельный экспортер для каждого сценария
                exporter = LoqiExporter()
                exporter.add_object(
                    situation := SituationState(
                        interruption_state=InterruptionType.NO_INTERRUPTION,
                    )
                )
                exporter.set_var("STATE", situation)

                # Используем add_trace вместо add_object, чтобы установить связи directlyBeforeOf
                exporter.add_trace(main_trace)

                # Добавляем пути между узлами
                if paths:
                    exporter.add_paths(paths)

                # Формируем имена файлов
                file_suffix = "" if scenario_name == "default" else f"_{scenario_name}"
                loqi_path = (genout_path / f"{file.stem}{file_suffix}.loqi").absolute()
                conditions_path = genout_path / f"{file.stem}{file_suffix}_conditions.json"
                trace_path = genout_path / f"{file.stem}{file_suffix}_trace.json"

                # Экспортируем LOQI файл
                exporter.export_cfg(cfg, str(loqi_path))
                exported_files.append(loqi_path)

                # Экспортируем информацию о назначенных значениях условий
                condition_decisions = export_condition_decisions(
                    main_trace, scenario_name=scenario_name
                )
                with open(conditions_path, "w", encoding="utf-8") as f:
                    json.dump(condition_decisions, f, indent=2, ensure_ascii=False)
                exported_files.append(conditions_path)

                # Экспортируем полную трассу
                trace_info = export_trace_acts(main_trace, scenario_name=scenario_name)
                with open(trace_path, "w", encoding="utf-8") as f:
                    json.dump(trace_info, f, indent=2, ensure_ascii=False)
                exported_files.append(trace_path)

            if SAVE_DEBUG_GRAPHS_PHG:
                # Визуализируем CFG в PNG (режим с рёбрами)
                png_path = (genout_path / f"{file.stem}-edge.png").absolute()
                visualize_cfg_graphviz(cfg, str(png_path))

                # Визуализируем CFG в PNG (режим с путями)
                png_pathinfo_path = (genout_path / f"{file.stem}-pathinfo.png").absolute()
                visualize_cfg_graphviz(cfg, str(png_pathinfo_path), paths_instead_of_edges=True)

                # Визуализируем CFG в PNG (режим с непрямыми путями)
                # png_indirect_paths_path = (genout_path / f"{file.stem}-indirect-paths.png").absolute()
                # visualize_cfg_graphviz(cfg, str(png_indirect_paths_path), paths_instead_of_edges=True, indirect_paths=True, paths=paths)

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
            for exported_file in exported_files:
                print(f"  {exported_file.name}: {exported_file}")
            print(f"  PNG (edges): {png_path}")
            print(f"  PNG (paths): {png_pathinfo_path}")
            # print(f"  PNG (indirect paths): {png_indirect_paths_path}")
