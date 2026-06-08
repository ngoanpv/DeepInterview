# DeepInterview Live Agent (WP-5)

Currently a shell that mirrors `packages/shared` as Pydantic v2 in
`src/deepinterview_agent/shared_models.py`. The contracts here are field-identical
(snake_case, same enums/defaults) with the Zod source of truth in
`packages/shared/src`; `tests/test_parity.py` enforces that against the generated
JSON Schemas in `packages/shared/schema`.

The LiveKit voice loop (cascaded STT -> LLM -> TTS) and the LangGraph prep/post
pipelines arrive in later WPs (WP-5 live interviewer, WP-6 prep, WP-7 scoring).
