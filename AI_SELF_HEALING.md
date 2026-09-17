# AI Self-Healing System

TrebelxMusic uses layered recovery instead of relying on a single AI patcher.

## Layer 1: deterministic recovery
Known compatibility/configuration failures are handled immediately. Examples:
- Kurigram rejecting legacy `quote=` arguments;
- missing optional `COOKIE_URL`;
- cookie loading from `YTDLP_COOKIES_B64`;
- startup syntax/deployment drift.

## Layer 2: AI repair
The error detector records runtime exceptions and forwards unknown failures to
the conservative AI healer when enabled. The healer:
- receives the traceback and relevant in-repository Python files;
- requests a minimal unified diff, not shell commands;
- accepts only Python files inside the repository;
- validates the patch before applying it;
- compiles the complete project after the patch;
- rolls back the affected files if validation fails;
- requests a clean restart after a validated repair.

## Railway variables
Automatic mode is enabled when an OpenAI key exists:

```text
AI_HEALER_ENABLED=auto
AI_HEALER_MODEL=gpt-5.6-luna
OPENAI_API_KEY=<your OpenAI API key>
```

To disable automatic AI repair:

```text
AI_HEALER_ENABLED=false
```

Deterministic recovery remains active when the AI layer is disabled.

## Cookie configuration
Cookies are optional. Preferred Railway variable:

```text
YTDLP_COOKIES_B64=<Base64 of your own Netscape cookies.txt>
```

`COOKIE_URL` remains supported for backwards compatibility. If neither is set,
TrebelxMusic continues without cookies instead of generating a startup/internal
error.

## Safety
No repair system can guarantee recovery from every third-party outage,
credential problem, Telegram permission issue, incompatible upstream API, or
hardware/runtime failure. Those cases are logged and surfaced for diagnosis.
