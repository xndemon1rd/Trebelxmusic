# TrabelxMusic AI providers

`/ai` uses the first configured provider in this order:

1. Gemini (`GEMINI_API_KEY`)
2. Groq (`GROQ_API_KEY`)
3. OpenAI (`OPENAI_API_KEY`, optional fallback)

Railway variables:

```text
GEMINI_API_KEY=...
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile
OPENAI_API_KEY=...
AI_MODEL=gpt-5.6-luna
```

Gemini and Groq are optional. If Gemini is unavailable, the bot automatically tries Groq; if both are unavailable and an OpenAI key is configured, it tries OpenAI.
