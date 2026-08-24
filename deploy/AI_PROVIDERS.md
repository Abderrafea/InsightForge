# AI providers and model selection

InsightForge supports the official Groq, OpenAI and Anthropic APIs. The agent graph
uses the same LLMProvider interface for all three; provider-specific clients and
structured-output formats stay inside adapters.

The welcome form offers a short list of suggested text models for each provider and
an **Other model** option. Users can enter an exact API model ID, including a snapshot
or account-specific model. This is not a full catalogue or a guarantee that the
account has access. A model must support the adapter's structured-output mechanism.
Audio/image-only models do not work with this dashboard workflow.

OpenAI uses structured function output, validated with the original Pydantic models.
Anthropic uses native JSON-schema output for current Claude models. Since native
schemas forbid arbitrary object keys, open dictionaries such as widget options are
encoded as JSON strings only on the provider wire, then restored and validated before
entering the agent state. Existing dashboard formats and validation stay unchanged.
Groq uses its existing structured tool-output adapter.

Suggestions are configured through VISITOR_MODELS (Groq), VISITOR_OPENAI_MODELS and
VISITOR_ANTHROPIC_MODELS. Set VISITOR_ALLOW_CUSTOM_MODELS=false to restrict selection
to suggestions. Otherwise the backend accepts a bounded model ID; users cannot set
an API base URL. Model availability is checked by the provider during the first
request. Invalid keys, inaccessible models, incompatible output configurations and
quota limits produce sanitized messages without provider payloads or secrets.

Public visitors supply a key for the selected provider. Changing providers clears
the entered key and resets consent. Keys never enter localStorage, sessionStorage,
cookies or database records. Each agent request carries the provider/model choice
and its key in the Authorization header. No server-key fallback is allowed for a
public visitor, and no automatic cross-provider failover occurs.

Hosting the app for free does not make provider API usage free. Access, credits and
charges depend on the visitor's provider account. API subscriptions and usage limits
must be checked in the provider's own console.

For private owner mode, configure AI_PROVIDER=groq|openai|anthropic, AI_MODEL, and the
corresponding GROQ_API_KEY, OPENAI_API_KEY or ANTHROPIC_API_KEY. The production helper
supports --provider and --model. Temperature is configurable for Groq; the new
OpenAI/Anthropic adapters retain model defaults for compatibility with reasoning
models that reject a caller-supplied temperature. Their output budget is bounded.

Adapter tests use mocked SDK responses and bind real schemas without network calls.
Live OpenAI/Anthropic account access is not claimed without testing those accounts.

References checked for the initial suggestions and output formats:

- [OpenAI models](https://developers.openai.com/api/docs/models)
- [OpenAI structured output](https://developers.openai.com/api/docs/guides/structured-outputs)
- [Claude models](https://platform.claude.com/docs/en/models/overview)
- [Claude structured output](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
