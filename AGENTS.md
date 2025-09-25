# Repository Guidelines

## Project Structure & Module Organization
Core logic is under `src/`: `bot.py` drives Telegram workflows, `github_client.py` polls releases, `version_manager.py` and `release_parser.py` maintain state, and shared helpers sit in `config.py`, `utils.py`, and `models/`. Runtime artifacts (cache, checkpoints, rotating logs) belong in `data/` and `logs/` and stay out of git. Windows launchers and `run.py` live at the top level, and long-form plans are collected in `docs/`. Tests mirror modules inside `tests/`.

## Build, Test, and Development Commands
- `python -m venv venv && venv\Scripts\activate`: prepare a sandboxed interpreter.
- `pip install -r requirements.txt`: install runtime, lint, and test dependencies.
- `python run.py` or `python simple_bot.py`: start the monitor in console mode.
- `pytest` / `pytest --cov=src`: execute the suite and view coverage.
- `black src tests` and `flake8 src tests`: auto-format and lint before committing.

## Coding Style & Naming Conventions
Stick to PEP 8 with four-space indentation, snake_case functions, PascalCase classes, and uppercase constants. Prefer explicit type hints on new surfaces that interact with `CCReleaseMonitorBot` or configuration loading. Keep modules cohesive; if a helper grows, lift it into `src/utils.py` or `src/models/` to match the current layout. Batch scripts follow the existing `start_*.bat` naming.

## Testing Guidelines
Pytest is required; add files as `tests/test_<module>.py` and mirror fixtures from `tests/test_config.py` when stubbing environment variables. Maintain or improve the current coverage when running `pytest --cov=src` and document any intentional gaps. Use `patch.dict` or lightweight fakes instead of hitting live APIs.

## Commit & Pull Request Guidelines
Use Conventional Commit prefixes (`feat`, `fix`, `refactor`, `chore`, etc.), matching existing history. Keep commits focused, describe observable behavior, and note config or interval changes explicitly. Pull requests should link issues, list validation steps (`pytest`, manual bot check), and attach screenshots when altering tray or Telegram replies.

## Configuration & Operations Notes
All secrets load from `.env`; sync any new keys into `.env.example` and mention defaults in the PR. Generated folders under `data/` and `logs/` stay untracked; extend `.gitignore` if new cache paths appear. When exposing remote approval or IPC ports, document port numbers in `docs/` and verify the bot still runs without the optional services.