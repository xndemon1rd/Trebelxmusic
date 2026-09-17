# TrebelxMusic deployment and self-healing

## Railway
This project deploys from the repository root with the included Dockerfile.
The launcher starts the BgUtils PO-token provider, validates the application,
and restarts the bot after unexpected exits with bounded backoff.

## Deterministic self-healing
`self_healer.py` runs before every bot boot. It:
- removes Python cache/bytecode artifacts;
- recreates required runtime directories;
- repairs known Docker/requirements drift;
- restores Deno when it is missing and the environment can safely install it;
- validates every Python source file with the AST parser;
- records a local `repair_report.json`.

The runtime `error_detector.py` also has deterministic compatibility repairs for
known failures such as legacy `quote=` calls against Kurigram and optional cookie
configuration errors. These repairs are deliberately narrow and do not execute
arbitrary remote instructions.

## AI-assisted repair
When `OPENAI_API_KEY` is present, `AI_HEALER_ENABLED=auto` enables the second
repair layer by default. Set `AI_HEALER_ENABLED=false` to disable it explicitly.
The AI layer is only used after deterministic handling has failed.

The AI repair flow:
1. captures the exception and traceback;
2. identifies only in-repository Python files from the traceback;
3. requests a minimal unified diff;
4. validates the patch before applying it;
5. restricts repairs to Python files inside the repository;
6. compiles the whole project after the change;
7. rolls back the affected files if validation fails;
8. requests a clean process restart after a validated repair.

Unknown third-party outages, invalid credentials, Telegram permissions, and
external API failures are reported rather than guessed at.
