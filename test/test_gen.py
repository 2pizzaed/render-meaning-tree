import json
import sys
import unittest
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.ast_analyzer import ASTNodeAnalyzer
from src.ast_managers import manage_code
from src.cfg import ASTNodeWrapper, CFGBuilder
from src.cfg.abstractions import (
    InterruptionType,
    SituationState,
    get_constructs_file_name,
    load_constructs,
)
from src.cfg.cfg import idgen
from src.cfg.cfg_graphviz import visualize_cfg_graphviz, write_dot
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
from src.coderenderer.html import prepare_html_context, render_static_html
from src.meaning_tree import convert, to_dict, to_tokens, to_dot
from src.qgen_utils import build_answer_objects_from_cfg
from src.runtime import (
    build_line_to_ast_id_for_conditions,
    enrich_trace_with_runtime,
    execute_with_trace,
    export_scenario_from_trace,
)
from src.types import SourceMap

INJECT_RUNTIME_VALUES = True

SAVE_DEBUG_GRAPHS_PNG = True

# Управление режимами генерации
AUTO_SAVE_SCENARIOS_TO_SOURCE = True  # Сохранять *_scenarios.json рядом с исходником
AUTO_REGENERATE_WITH_SCENARIOS = True  # Сразу использовать сгенерированный сценарий
GENERATE_SCENARIOS_ONLY = False  # Только создать сценарии, без задач
GENERATE_TASKS_ONLY = False  # Только задачи, без генерации сценариев


def _run_runtime_trace(code: str, file_path: Path, ast: ASTNodeAnalyzer):
    # Строим маппинг line -> ast_id для условий
    line_to_ast_id = build_line_to_ast_id_for_conditions(ast)
    return execute_with_trace(
        code,
        filename=str(file_path),
        track_conditions=True,
        line_to_ast_id=line_to_ast_id,
    )


def load_or_generate_scenarios(
    file_path: Path,
    code: str,
    language: str,
    ast: ASTNodeAnalyzer,
    scenarios_file: Path,
    runtime_trace,
    allow_generate: bool,
) -> tuple[list[dict[str, Any]] | None, bool]:
    scenario_plans = None
    generated = False

    if scenarios_file.exists():
        scenario_plans = load_scenarios_from_file(scenarios_file)
        return scenario_plans, generated

    if not allow_generate:
        return scenario_plans, generated

    if language != "python":
        print("  Info: Skip scenario auto-generation for non-Python file.")
        return scenario_plans, generated

    if not AUTO_SAVE_SCENARIOS_TO_SOURCE:
        return scenario_plans, generated

    try:
        trace = runtime_trace or _run_runtime_trace(code, file_path, ast)

        if trace.exception:
            print(f"  Warning: Runtime execution failed: {trace.exception}")

        if trace.events:
            scenario = export_scenario_from_trace(
                trace,
                scenario_name="default",
                ast_analyzer=ast,
            )
            with open(scenarios_file, "w", encoding="utf-8") as f:
                json.dump(scenario, f, indent=2, ensure_ascii=False)
            scenario_plans = [scenario]
            generated = True
            print(
                f"  Generated scenario: {scenarios_file.name} -> {scenarios_file}"
            )
        else:
            print("  Warning: Runtime trace has no events; scenario not saved.")
    except Exception as e:
        print(f"  Warning: Could not execute code for runtime tracing: {e}")

    return scenario_plans, generated

class TestComplexProblemBuild(unittest.TestCase):
    def test_generate(self):
        current_dir = Path(__file__).parent

        # Путь к папке с входными данными и выходной папке
        task_data_path = current_dir / "data" / "task_code" #  / "debug"
        genout_path = current_dir / "output" / "code_snippets" #  / "debug"
        genout_path.mkdir(parents=True, exist_ok=True)

        # Загружаем конструкции
        constructs = load_constructs(get_constructs_file_name())

        files = task_data_path.iterdir()
        # files = [task_data_path / "2_functions.py"]

        generate_scenarios = True
        generate_tasks = True
        if GENERATE_SCENARIOS_ONLY and GENERATE_TASKS_ONLY:
            print("Warning: Both GENERATE_SCENARIOS_ONLY and GENERATE_TASKS_ONLY are True; running both.")
        elif GENERATE_SCENARIOS_ONLY:
            generate_tasks = False
        elif GENERATE_TASKS_ONLY:
            generate_scenarios = False

        # Перебираем все файлы в task_data
        for file in files:
            # Начинаем нумерацию узлов с начала для каждого файла, таким образом, порядок обработки файлов не влияет на id узлов.
            idgen.reset()
            ###
            if file.stem not in (
                file.stem,  # NO FILTERING
                # '1_onefunc_while'
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

            source_map: SourceMap | None = convert(
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

            if False:
                ast_dot_path = genout_path / f"{file.stem}_ast.dot"
                ast_dot = to_dot(language, code)
                with open(ast_dot_path, "w", encoding="utf-8") as f:
                    f.write(ast_dot)

            ast = ASTNodeAnalyzer(ast_json, source_map) # type: ignore
            tokens = to_tokens(
                language, source_map["source_code"]) # type: ignore
            if tokens is None:
                self.fail(f"Failed to tokenize code for {file.name}")
            manager = manage_code(tokens, source_map)

            tok_json_path = genout_path / f"{file.stem}_tokens.json"
            with open(tok_json_path, "w", encoding="utf-8") as f:
                json.dump(tokens, f, indent=2, ensure_ascii=False)

            html_context = prepare_html_context(manager)
            html = render_static_html(html_context, snippet_only=True)

            # Создаём ASTNodeWrapper
            program_root = ASTNodeWrapper(ast_node=ast_json, _astnodeanalyzer=ast)

            b = CFGBuilder(constructs)

            # Генерируем CFG
            cfg = b.make_cfg_for_ast(program_root)

            if cfg is None:
                self.fail(f"Failed to build CFG for {file.name}")

            # Оптимизируем CFG
            cfg.optimize()

            runtime_trace = None
            if INJECT_RUNTIME_VALUES and language == "python":
                try:
                    runtime_trace = _run_runtime_trace(code, file, ast)
                    if runtime_trace.exception:
                        print(f"  Warning: Runtime execution failed: {runtime_trace.exception}")
                except Exception as e:
                    print(f"  Warning: Could not execute code for runtime tracing: {e}")

            scenarios_file = current_dir / "data" / "task_code" / f"{file.stem}_scenarios.json"
            scenario_plans, generated_scenario = load_or_generate_scenarios(
                file,
                code,
                language,
                ast,
                scenarios_file,
                runtime_trace,
                generate_scenarios,
            )

            if generated_scenario and not AUTO_REGENERATE_WITH_SCENARIOS:
                scenario_plans_for_tasks = None
                print("  Info: Scenario saved but not used (AUTO_REGENERATE_WITH_SCENARIOS=False).")
            else:
                scenario_plans_for_tasks = scenario_plans

            if not generate_tasks:
                print("  Info: Task generation skipped (GENERATE_SCENARIOS_ONLY=True).")
                continue

            if scenario_plans_for_tasks:
                scenarios = [
                    plan_to_scenario_config(plan, cfg) for plan in scenario_plans_for_tasks
                ]
            else:
                scenarios = [
                    TraceScenarioConfig(name="default", seed=DEFAULT_SEED),
                ]

            trace_results = generate_trace_variants(cfg, scenarios)
            # self.assertTrue(len(trace_results) > 0)
            if not trace_results:
                print(f"Failed to generate traces for {file.name}", file=sys.stderr)
                continue

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

            if SAVE_DEBUG_GRAPHS_PNG:
                # Визуализируем CFG в PNG (режим с рёбрами)
                png_path = (genout_path / f"{file.stem}-edge.png").absolute()
                dot_path = (genout_path / f"{file.stem}-edge.dot").absolute()
                cfg_edges_graph = visualize_cfg_graphviz(cfg)
                write_dot(cfg_edges_graph, dot_path)
                write_dot(cfg_edges_graph, png_path)

                # Визуализируем CFG в PNG (режим с путями)
                png_pathinfo_path = (genout_path / f"{file.stem}-pathinfo.png").absolute()
                dot_pathinfo_path = (genout_path / f"{file.stem}-pathinfo.dot").absolute()
                cfg_paths_graph = visualize_cfg_graphviz(cfg, paths_instead_of_edges=True)
                write_dot(cfg_paths_graph, png_pathinfo_path)
                write_dot(cfg_paths_graph, dot_pathinfo_path)

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
            if SAVE_DEBUG_GRAPHS_PNG:
                print(f"  PNG (edges): {png_path}")
                print(f"  PNG (paths): {png_pathinfo_path}")
                # print(f"  PNG (indirect paths): {png_indirect_paths_path}")
