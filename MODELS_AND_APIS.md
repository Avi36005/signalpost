# Models and APIs

No model is enabled. No prompts are sent to an LLM and no machine-generated labels are used as independent truth. Synthesis is `aviscope-deterministic-v1` over accepted claims.

Enabled network provider: Brønnøysundregistrene public REST APIs, with endpoint templates in `aviscope/pipeline.py`. These calls need no API key. Source configuration is frozen by SHA-256 per run.

Disabled: Brave/Bing/Google search, OpenAI/Anthropic/other model APIs, JBOX, social/jobs/news/traffic/review platforms, browser automation in the crawler, sentiment, GPU inference. The reference starter contains experimental connectors; the AviScope evaluator never invokes them. Optional dependency groups in the preserved starter are not proof of use.

Required credential environment variables: **none**. `AVISCOPE_DATA_DIR` selects local data for the server; it is not a secret. `.env.example` contains no credentials. No provider secret may be placed in the frontend. Add a paid provider only with reviewed terms, explicit development budget, exact model/version and worst-case call reservation through the shared broker.
