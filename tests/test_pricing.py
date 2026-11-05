import httpx
import pytest
from agentkit.errors import PricingError
from agentkit.llm.pricing import apply_groq_cache_pricing, cost_usd, fetch_groq_rates, parse_groq_models

MODELS = """
| [![OpenAI](logo.svg)GPT OSS 120B](/docs/model/openai/gpt-oss-120b)openai/gpt-oss-120b | 500 | $0.15 input$0.60 output | 250K TPM |
| [![OpenAI](logo.svg)GPT OSS 20B](/docs/model/openai/gpt-oss-20b)openai/gpt-oss-20b | 1000 | $0.075 input$0.30 output | 250K TPM |
| [![Meta](logo.png)Llama 3.3 70B](/docs/model/llama-3.3-70b-versatile)llama-3.3-70b-versatile | 280 | ContactSales | ContactSales |
| [![OpenAI](logo.svg)Whisper](/docs/model/whisper-large-v3)whisper-large-v3 | - | $0.111 per hour | 200K ASH |
"""

CACHING = """
## [Supported Models](#supported-models)

| Model ID | Model |
| --- | --- |
| openai/gpt-oss-120b | [GPT-OSS 120B](https://console.groq.com/docs/model/openai/gpt-oss-120b) |
| openai/gpt-oss-20b | [GPT-OSS 20B](https://console.groq.com/docs/model/openai/gpt-oss-20b) |

## [Pricing](#pricing)

There is a 50% discount for cached input tokens.

## [Structuring Prompts](#structuring-prompts)
"""

def test_parser_keeps_token_prices_and_skips_other_units():
    rates = parse_groq_models(MODELS)
    assert set(rates) == {'openai/gpt-oss-120b', 'openai/gpt-oss-20b'}
    assert rates['openai/gpt-oss-120b'].input == 0.15
    assert rates['openai/gpt-oss-120b'].output == 0.60
    assert rates['openai/gpt-oss-20b'].input == 0.075

def test_cache_discount_comes_from_the_caching_page():
    rates = apply_groq_cache_pricing(parse_groq_models(MODELS), CACHING)
    assert rates['openai/gpt-oss-120b'].cached_input == pytest.approx(0.075)
    assert rates['openai/gpt-oss-20b'].cached_input == pytest.approx(0.0375)

def test_cost_uses_the_parsed_table():
    rates = apply_groq_cache_pricing(parse_groq_models(MODELS), CACHING)
    assert cost_usd('openai/gpt-oss-120b', 1_000_000, 1_000_000, rates=rates) == pytest.approx(0.75)
    cached = cost_usd('openai/gpt-oss-120b', 1_000_000, 0, cached_input_tokens=1_000_000, rates=rates)
    assert cached == pytest.approx(0.075)

def test_unknown_model_and_broken_pages():
    rates = parse_groq_models(MODELS)
    with pytest.raises(PricingError, match='llama-3.3-70b-versatile'):
        cost_usd('llama-3.3-70b-versatile', 1, 1, rates=rates)
    with pytest.raises(PricingError):
        parse_groq_models('| no prices here |')
    with pytest.raises(PricingError):
        apply_groq_cache_pricing(rates, 'no discount mentioned')

def test_fetch_reads_both_live_documents():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith('models.md'):
            return httpx.Response(200, text=MODELS)
        if request.url.path.endswith('prompt-caching.md'):
            return httpx.Response(200, text=CACHING)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    rates = fetch_groq_rates(client=client, models_url='https://groq.test/models.md', caching_url='https://groq.test/prompt-caching.md')
    assert rates['openai/gpt-oss-20b'].output == 0.30
    assert rates['openai/gpt-oss-20b'].cached_input == pytest.approx(0.0375)

def test_fetch_failure_is_a_pricing_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(PricingError, match='models.md'):
        fetch_groq_rates(client=client, models_url='https://groq.test/models.md', caching_url='https://groq.test/prompt-caching.md')