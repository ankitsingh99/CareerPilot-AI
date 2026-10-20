import pytest
from unittest.mock import patch, MagicMock
from intelligence.llm_clients.openrouter import (
    DEFAULT_FREE_MODEL,
    FREE_MODELS_POOL,
    is_free_model,
    fetch_free_models,
    get_free_models,
    ask,
)


def test_default_free_model_is_valid():
    assert is_free_model(DEFAULT_FREE_MODEL)
    assert DEFAULT_FREE_MODEL.endswith(":free")


def test_is_free_model():
    # Valid free tier endpoints
    assert is_free_model("cohere/north-mini-code:free") is True
    assert is_free_model("google/gemma-4-31b-it:free") is True
    assert is_free_model("openrouter/free") is True
    assert is_free_model("auto") is True
    assert is_free_model("any") is True

    # Disallowed billable / non-free endpoints
    assert is_free_model("openai/gpt-4o") is False
    assert is_free_model("anthropic/claude-3.5-sonnet") is False
    assert is_free_model("meta-llama/llama-3-70b-instruct") is False
    assert is_free_model("") is False


def test_fetch_free_models_structure():
    models = fetch_free_models()
    assert isinstance(models, list)
    assert len(models) > 0
    for model in models:
        assert is_free_model(model), f"Model {model} must satisfy zero-cost free endpoint rule"


def test_ask_blocks_paid_models():
    with pytest.raises(ValueError, match="Strict Zero-Cost Violation"):
        ask("test prompt", model="openai/gpt-4o")

    with pytest.raises(ValueError, match="Strict Zero-Cost Violation"):
        ask("test prompt", model="anthropic/claude-3-opus")


def test_fetch_free_models_caching():
    # In-memory cached result should match
    m1 = fetch_free_models()
    m2 = fetch_free_models()
    assert m1 == m2


def test_sync_free_models_generates_file(tmp_path):
    from tools.sync_free_models import sync, OUTPUT_FILE
    target = tmp_path / "test_models.txt"
    ret = sync(output_path=target)
    assert ret == 0
    assert target.exists()

    content = target.read_text(encoding="utf-8")
    assert "OpenRouter Zero-Cost Free Models Catalog" in content
    assert "cohere/north-mini-code:free" in content
    assert "openrouter/free" in content
