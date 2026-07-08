# Project Agent Instructions

## Skills To Use

- When working with AST, Meaning Tree output, language translators, semantic nodes, serializers, or the embedded `meaning_tree/` project, use the `meaning-tree` skill. Prefer local project sources and local Maven source jars over memory or external documentation.
- When diagnosing, explaining, extending, or validating the reasoner, thought process graphs, `.tpg` files, `.loqi` domain/tree files, DomainSolvingModel data, or CompPrehension reasoning behavior, use the `thought-process-graph` skill.
- For syntax-sensitive TPG/LOQI work, ground conclusions in documentation or source code before proposing code. Use the skill references and, when needed, inspect the current TPG/LOQI grammar, builder/writer code, reasoner code, and local domain files.

## TPG And LOQI Safety

- Do not modify `.tpg` or `.loqi` files without explicit developer approval for that specific change.
- For `.tpg` and `.loqi` requests, default to diagnosis: explain the suspected issue, cite the relevant file/construct, and propose a patch or replacement snippet for developer review.
- Before recommending TPG/LOQI code, check that the syntax and constructs are valid for the current project. Validate against the relevant documentation, grammar, source implementation, or available conversion/validation tooling.
- If a proposed reasoner/domain change cannot be validated locally, say exactly what was checked and what remains unverified.

## Validation And Testing

Use `uv` for project commands.

- `uv run pytest` - run the test suite.
- `uv run ruff check .` - lint Python code and import ordering.
- `uv run pyright` - type-check Python code.
- `uv run find-correct-trace-actions` - inspect the sequence of actions produced by the `findCorrect` reasoning flow for a code snippet.
- `uv run render-construct-automaton` - render a construct transition automaton from construct rules for debugging rule flow.
- `uv run tree-loqi-to-xml` - convert a TPG/LOQI tree file to XML for syntax/build diagnostics.

Run only the checks that are required by the task and the risk of the change. For small, local edits, prefer the narrowest relevant test, script, or validator instead of the full suite. If a change is broad, touches shared behavior, or affects core generation/reasoning paths, run the relevant test file; for large or cross-cutting changes, run `uv run pytest`.

When changing Python code, run `ruff` and `pyright` when feasible, especially for non-trivial edits. When changing reasoning/domain behavior, also run the narrow script or validator that exercises the affected graph, LOQI file, or construct.

## Toolchain MCP

The project registers the CompPrehension toolchain MCP server.
If that MCP is unavailable, check the local RPC server first:

- `bash rpc_server.sh status`
- If it is not running, start it with `bash rpc_server.sh start`

## Code Hygiene

- Keep Python changes typed and consistent with existing module patterns.
- Prefer small, focused edits over broad refactors.
- When adding new code, reuse existing helper modules instead of re-implementing the same utility logic; in tests, prefer `test/helpers` utilities over new local helpers.
- Preserve generated/domain artifacts unless the developer explicitly asks to regenerate or update them.
