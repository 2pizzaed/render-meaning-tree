# Project Agent Instructions

## Skills To Use

- When working with AST, Meaning Tree output, language translators, semantic nodes, or serializers, use the `meaning-tree` skill. Inspect implementation sources in the `meaning_tree/` submodule or local Maven source jars only to investigate a problem in the Meaning Tree implementation.
- When diagnosing, explaining, extending, or validating the reasoner, thought process graphs and their `.tpg` files, `.loqi` domain data-model files, or CompPrehension reasoning behavior, use the `thought-process-graph` skill.
- For syntax-sensitive TPG/LOQI work, ground conclusions in documentation or source code before proposing code. Use the skill references and, when needed, inspect the current TPG/LOQI grammar, builder and writer code, reasoner code, and local domain files.

## Behavior Rules

- Before adding any new functionality or changing existing functionality, gather the necessary context and documentation and think the change through. The solution may fit in far fewer lines, or the user may not realize the scale of the change and the problems it can cause. If you notice this, do not start the work; first agree it with the user and make sure they understand what the change actually is.
- A user request is not the final word: the user can be mistaken. If you notice that, say so and clarify it with them.
- Messages to the user must be clear and understandable for the task at hand, and not overloaded with extra text.
- Do not modify `.tpg` or `.loqi` files without explicit developer approval for that specific change.
- The same approval rule applies to all diagrams (including every file under `docs/diagrams/`) and TPG documentation: `docs/check_graph_idea.md`, `docs/findCorrect_graph_idea.md` and any other `docs/` file describing thought process graphs. Propose changes for review instead of editing these files.
- For `.tpg` and `.loqi` requests, default to diagnosis: explain the suspected issue, cite the relevant file or construct, and propose a patch or replacement snippet for developer review.
- Before recommending TPG/LOQI code, check that the syntax and constructs are valid for the current project. Validate against the relevant documentation, grammar, source implementation, or available conversion and validation tooling.
- Before proposing a concrete `.tpg` change, use the `thought-process-graph` skill's `model` route and its `references/modeling-principles.md` to assess the rationale, readability, graph complexity, and effect on explanations and pedagogical questions. Prefer the smallest understandable change that expresses the underlying domain rule. Reject unnecessary branches, duplicated checks, and workarounds that merely make the current example pass or hide a defect elsewhere.
- Briefly justify the proposed TPG change: which reasoning rule it represents, why existing graph logic cannot be reused or adjusted more simply, and why any added complexity is necessary. Syntax validation alone is insufficient.
- If a proposed reasoner or domain change cannot be validated locally, say exactly what was checked and what remains unverified.

## TPG Explanation Quality

1. For `conclude: error/false`, explain the selected answer's error without revealing the correct answer; identify the selected object or location when helpful.
2. Explain the domain rule and its application to the situation, using only causes established by the graph's checks.
3. Avoid vague «то»/«там»; use «этот»/«эти» only with clear referents. Prefer localized object names via substitutions such as `${A}[case='р']`.
4. Write for beginners; terms already used in action and object names may be assumed familiar. Avoid internal engine terminology.
5. Use short, direct sentences without tautology or unnecessary repetition; clarity takes priority over brevity.

Check the rendered text with actual names and case modifiers, and keep RU/EN meanings aligned.

## Validation And Testing

Use `uv` for project commands.

Use pytest for routine validation. Run the playground e2e check only when the user explicitly asks for it, and only on the dataset or input files they specified. Do not substitute another dataset or expand the requested dataset. If the requested dataset is unclear, clarify it before running e2e.

When checking existing TPG behavior on a snippet outside the test cases, analyze the scenario and add a self-contained case to the relevant tests using inline code or an existing fixture. Do not create a snippet file just to run tests or make tests depend on a path to the example file.

- `uv run pytest` - run the test suite without playground e2e; prefer specific relevant test files for focused changes.
- `uv run pytest -m e2e` - run the excluded playground e2e checks.
- `uv run ruff check .` - lint Python code and import ordering.
- `uv run pyright` - type-check Python code.
- `uv run find-correct-trace-actions` - inspect the sequence of actions produced by the `findCorrect` reasoning flow for a code snippet.
- `uv run render-construct-automaton` - render a construct transition automaton from construct rules for debugging rule flow.
- `uv run generate-problems` (same as `uv run main.py`) - generate learning problems for a code snippet and print the selected ones; `--output DIR` saves them as CompPrehension question JSON files; `--target-language LANG` generates problems on the MeaningTree translation of the snippet.
- `uv run playground` - start the Flask playground (`test/playground/app.py`). Reason and Hint continue from the exported LOQI of the longest already accepted trace prefix (in-memory cache keyed by situation, `domain/` file mtimes and prefix steps); the `No cache` checkbox in Answer Trace (`no_cache: true` in `/reason-trace` and `/hint-trace`) rechecks the whole trace step by step.
- `uv run playground-e2e FILE [--seed N] [--limit N] [--no-cache] [--language LANG] [--target-language LANG]` - e2e check of the playground for a snippet without a running server (`test/tools/playground_e2e.py`): presses action buttons with Reason until the graph reports the finished program (`everything_evaluated`; more than `--limit` accepted steps is an error), then checks that Hint suggests the same action on every step; prints the accepted action order. `--target-language` translates the snippet as the playground translation selector does.
- `uv run render-code-html (FILE | --stdin --lang LANG) [-o OUT] [--no-buttons] [--no-style] [--no-icon-styles]` - render a code snippet to static HTML (`templates/code_component.html`) and print it to stdout (UTF-8) or write it to `-o`; the language of FILE is taken from its extension unless `--lang` is given; the output starts with a Remix Icon CDN stylesheet link for button icons unless `--no-buttons` or `--no-icon-styles` (`src/cli/render_code_html.py`).
- `uv run annotate-trace` - run a Python snippet and print it with `<! … >` value markers built from its real execution trace (`test/tools/annotate_trace.py`).
- `uv run tree-loqi-to-xml` - convert a TPG/LOQI tree file to XML for syntax and build diagnostics.

Run only the checks that are required by the task and the risk of the change. For small, local edits, prefer the narrowest relevant test, script, or validator instead of the full suite. If a change is broad, touches shared behavior, or affects core generation or reasoning paths, run the relevant test file; for large or cross-cutting changes, run `uv run pytest`.

When changing Python code, run `ruff` and `pyright` when feasible, especially for non-trivial edits. When changing reasoning or domain behavior, also run the narrow script or validator that exercises the affected graph, LOQI file, or construct.

## Toolchain MCP

The project registers the CompPrehension toolchain MCP server.
If that MCP is unavailable, check the local RPC server first:

- `bash rpc_server.sh status`
- If it is not running, start it with `bash rpc_server.sh start`

Tip: Use Git Bash on Windows.

When running tests that exercise Meaning Tree and TPG, RPC mode must be enabled.

## Code Hygiene

- Keep Python changes typed and consistent with existing module patterns.
- Prefer small, focused edits over broad refactors.
- Before adding helpers or any other code, search the existing code for the same or similar behavior and assess reuse or a small, focused adaptation. Add new code only after checking that no suitable implementation exists or can be reused with a small change; in tests, check `test/helpers` first.
- Introduce private helper functions or methods (`_...`) only when they reduce overall code volume and improve readability. Each must have one clear responsibility, a descriptive name, and a concise docstring stating its purpose. Avoid helpers that merely move code elsewhere or add an unnecessary layer of indirection.

## Solution Quality Review

- Before completing a task, review all solutions created or changed during the session for correctness, readability, cognitive load, and impact on project complexity. Resolve issues within the task scope before reporting completion.
- Avoid unnecessary abstractions, indirection, configuration options, dependencies, and duplication; any added complexity must be justified by the task's requirements. The code must be easy to understand, have clear names, and stay straightforward to extend by hand.
- Keep comments concise and understandable to a human reader. Explain non-obvious intent, constraints, or tradeoffs rather than restating the code.

## Project Documentation

- Record important, lasting information from the task in the relevant existing document under `docs/` (TPG documentation only with explicit approval), including behavior changes, design decisions, constraints, and usage or maintenance instructions. Keep documentation focused and consistent with the final implementation.
- Create new documents under `docs/` only with explicit user approval. If no suitable existing document is available, propose a filename and purpose and request approval before creating it.
- If a documentation change is agreed, keep it concise and not overloaded in meaning, yet fully understandable, without interpretations that make sense only to the agent within its session.
