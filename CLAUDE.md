# CLAUDE.md

## Rules

**Never** push or commit without asking the user.

## What This Project Is

Two deliverables from one repo:

1. **ROS2 Package Index** — Pre-built JSON files covering every package across 6 ROS2 distributions (foxy, galactic, humble, iron, jazzy, kilted — 8,355 packages total). Deployed to GitHub Pages. Contains metadata, dependencies (all 9 types + reverse deps), and full message/service/action interface definitions.

2. **MCP Server** (`ros2-index-mcp`) — A FastMCP server that exposes the index to LLMs. Lets Claude look up packages, search by topic, read interface field definitions, and understand dependency graphs while writing ROS2 code.

The development environment is the **indexer** (`ros2_indexer/`): the pipeline that clones repos, parses package.xml and .msg/.srv/.action files, and serializes the JSON index. The MCP server (`mcp_server/`) is the consumer-facing layer on top.

## Package Manager: uv

This project uses **uv** exclusively. Not pip, not poetry.

```bash
cd ros2_parser
uv sync --extra dev              # Install everything
uv run pytest                    # Run all tests
uv run pytest -m "not integration"  # Skip network tests
uv run pytest -m integration     # Network tests only
uv run ros2-indexer build --distro jazzy --package sensor_msgs --keep-scratch
uv run ros2-indexer crossref --distro jazzy
uv run ros2-index-mcp            # Start the MCP server
```

Always use `--keep-scratch` during development so `.scratch/` persists for debugging.

## Architecture

```
ros2_parser/
├── src/
│   ├── ros2_indexer/            # Indexer pipeline (build-time)
│   │   ├── cli.py               # Typer CLI: build + crossref commands
│   │   ├── fetchers/distro.py   # distribution.yaml → package-to-repo mapping
│   │   ├── fetchers/repo.py     # Shallow git clone with tag→v-tag→branch fallback
│   │   ├── parsers/package_xml.py  # package.xml → PackageMetadata
│   │   ├── parsers/messages.py  # .msg/.srv/.action → structured definitions
│   │   ├── models.py            # All dataclasses
│   │   ├── serializer.py        # JSON output: per-package + packages.json + distros.json
│   │   └── config.py            # Paths and URL templates
│   └── mcp_server/              # MCP server (runtime)
│       ├── server.py            # FastMCP app, 5 tools
│       ├── loader.py            # HTTP fetch (GitHub Pages) + local fallback + cache
│       └── distro.py            # Distro name validation
├── tests/                       # Indexer tests
├── index/                       # Built output (gitignored, deployed to gh-pages via scripts/deploy-index.sh)
│   ├── distros.json             # ["jazzy", ...] — source of truth for list_distros
│   └── {distro}/
│       ├── packages.json
│       └── {package}.json
└── pyproject.toml
```

## MCP Server Tools

5 tools, designed for minimal token cost and agentic workflows:

| Tool | Purpose |
|------|---------|
| `set_distro(distro)` | Set session distro. LLM should call this FIRST. |
| `list_distros()` | What distros are indexed (reads distros.json) |
| `search_packages(query)` | Returns `[{name, description}]` — max 20 results |
| `get_package(package)` | Metadata + deps + interface NAMES (not definitions) |
| `get_message(package, message)` | Single interface with structured fields (no raw by default) |

After `set_distro`, the `distro` parameter is optional on all other tools.

## Testing

### Unit tests (90 total, no network)

```bash
uv run pytest -m "not integration"
```

Covers: distro validation, index loading, all 5 MCP tools (via FastMCP in-process client), crossref correctness + idempotency, repo clone fallback chain.

### Integration tests (local index)

```bash
uv run pytest -m integration
```

Hits the real local index at `ros2_parser/index/`.

### Testing the MCP server with subagents

The MCP server is configured in `.claude/settings.json` for this project. To test it, spawn a subagent within a Claude Code session — do NOT use the Anthropic API. The subagent inherits the MCP server connection:

```
# In Claude Code, spawn a Haiku subagent:
Agent(model="haiku", prompt="I'm on ROS2 jazzy. What fields does sensor_msgs/Image have?")
```

The subagent should call `set_distro("jazzy")` → `get_message("sensor_msgs", "Image")` and return the field list. Test multiple scenarios:
- Package search: "Find packages for working with LIDAR"
- Cross-package type resolution: "What fields does the nested PoseStamped in NavigateToPose feedback contain?"
- Dependency investigation: "How many packages depend on tf2_msgs?"
- Build help: "What do I need in package.xml to use sensor_msgs?"

### Linting

Pre-commit hooks run ruff automatically. Manual:

```bash
uv run ruff check .              # Lint
uv run ruff check . --fix        # Auto-fix
uv run ruff format .             # Format
```

## Critical Gotchas

- **distribution.yaml `version` = branch name** (e.g. `jazzy`), not semver. See `fetchers/distro.py`.
- **Package name ≠ repo name**: `sensor_msgs` lives in `common_interfaces`. The indexer builds a reverse lookup from distribution.yaml.
- **Many packages share one repo**: Clone once, parse each subdirectory.
- **Version resolution**: tag → v-prefix tag → branch. Timeout is 120s per clone.
- **distros.json is built by the indexer** (`serializer.py:write_distros_json`). The MCP server reads from it via GitHub Pages. When adding a new distro, run the indexer then `scripts/deploy-index.sh`.

## Documentation

Update the README.md after finishing a step, or before commiting.

## Current State

- **6 distros indexed**: foxy (1,060), galactic (908), humble (1,881), iron (1,240), jazzy (1,768), kilted (1,498) — 8,355 packages total.
- **Index is gitignored on main**, deployed to `gh-pages` via `scripts/deploy-index.sh`. Main stays code-only.
- **Index is always built locally**, never by CI. Deploy with `scripts/deploy-index.sh` after building.

## Future Steps

- **Simplify installation**: Document `fastmcp install claude-code` as the primary install method.

## Style Preferences

- No unnecessary abstractions. Three similar lines are better than a premature helper.
- No speculative features or "nice to have" additions.
- Critique before implementing — discuss trade-offs, check what actually applies.
- Test with real agentic scenarios (subagents), not just unit tests.
- Keep token cost low in MCP responses — strip `raw` fields by default, return names instead of full objects where possible.
- Run `/simplify` after significant changes to catch reuse and quality issues.
- Lean documentation in README, fit for human and LLM readability
- README with single fenced code blocks. No comments inside code blocks - allows for copy button of commands directly from github
- Clear seperation of devliverable (MCP server / index) and development project parts (the indexer logic)
