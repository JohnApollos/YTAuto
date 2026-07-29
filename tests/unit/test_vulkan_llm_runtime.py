import pytest
from unittest.mock import patch, MagicMock
import requests
from autonomous_media.runtime.vulkan_llm_runtime import VulkanLLMRuntime, parse_prompt_to_messages
from autonomous_media.runtime.manager import ResourceProfile, InferenceRequest
from autonomous_media.exceptions import ModelTimeoutError, StageUnrecoverableError

def test_parse_prompt_to_messages():
    # Prompt with SYSTEM: and USER:
    prompt = "SYSTEM:\nYou are a helpful assistant.\nUSER:\nHello there!"
    messages = parse_prompt_to_messages(prompt)
    assert len(messages) == 2
    assert messages[0] == {"role": "system", "content": "You are a helpful assistant."}
    assert messages[1] == {"role": "user", "content": "Hello there!"}

    # Prompt with lowercase tags
    prompt_lower = "system:\nHelp assistant.\nuser:\nHi"
    messages_lower = parse_prompt_to_messages(prompt_lower)
    assert len(messages_lower) == 2
    assert messages_lower[0] == {"role": "system", "content": "Help assistant."}
    assert messages_lower[1] == {"role": "user", "content": "Hi"}

    # Prompt without tags
    prompt_raw = "Just a standard prompt text."
    messages_raw = parse_prompt_to_messages(prompt_raw)
    assert len(messages_raw) == 1
    assert messages_raw[0] == {"role": "user", "content": "Just a standard prompt text."}

def test_vulkan_llm_runtime_load_success():
    profile = ResourceProfile(ram_mb=4000, vram_mb=4000, backend="vulkan", quantization="Q4_K_M")
    runtime = VulkanLLMRuntime(name="qwen3", resource_profile=profile)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    with patch("requests.get", return_value=mock_response) as mock_get:
        runtime.load()
        mock_get.assert_called_once_with("http://localhost:8080/health", timeout=5.0)

def test_vulkan_llm_runtime_load_failure():
    profile = ResourceProfile(ram_mb=4000, vram_mb=4000, backend="vulkan", quantization="Q4_K_M")
    runtime = VulkanLLMRuntime(name="qwen3", resource_profile=profile)
    
    # Non-200 response
    mock_response = MagicMock()
    mock_response.status_code = 500
    with patch("requests.get", return_value=mock_response):
        with pytest.raises(StageUnrecoverableError):
            runtime.load()

    # Connection failure
    with patch("requests.get", side_effect=requests.RequestException("Connection refused")):
        with pytest.raises(StageUnrecoverableError):
            runtime.load()

def test_vulkan_llm_runtime_infer_success():
    profile = ResourceProfile(ram_mb=4000, vram_mb=4000, backend="vulkan", quantization="Q4_K_M")
    runtime = VulkanLLMRuntime(name="qwen3", resource_profile=profile)
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Inference result text"
                }
            }
        ]
    }
    
    request = InferenceRequest(prompt="SYSTEM:\nSystem rule\nUSER:\nUser prompt")
    with patch("requests.post", return_value=mock_response) as mock_post:
        res = runtime.infer(request, timeout_s=30.0)
        assert res.text == "Inference result text"
        assert res.model_name == "qwen3"
        mock_post.assert_called_once_with(
            "http://localhost:8080/v1/chat/completions",
            json={
                "model": "qwen3",
                "messages": [
                    {"role": "system", "content": "System rule"},
                    {"role": "user", "content": "User prompt"}
                ],
                "temperature": 0.7,
                "max_tokens": 2048
            },
            timeout=30.0
        )

def test_vulkan_llm_runtime_infer_timeout():
    profile = ResourceProfile(ram_mb=4000, vram_mb=4000, backend="vulkan", quantization="Q4_K_M")
    runtime = VulkanLLMRuntime(name="qwen3", resource_profile=profile)
    
    request = InferenceRequest(prompt="test prompt")
    with patch("requests.post", side_effect=requests.Timeout("Request timed out")):
        with pytest.raises(ModelTimeoutError):
            runtime.infer(request, timeout_s=10.0)

def test_vulkan_llm_runtime_infer_error():
    profile = ResourceProfile(ram_mb=4000, vram_mb=4000, backend="vulkan", quantization="Q4_K_M")
    runtime = VulkanLLMRuntime(name="qwen3", resource_profile=profile)
    
    request = InferenceRequest(prompt="test prompt")
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    with patch("requests.post", return_value=mock_response):
        with pytest.raises(StageUnrecoverableError):
            runtime.infer(request, timeout_s=10.0)

def test_vulkan_llm_runtime_health_check():
    profile = ResourceProfile(ram_mb=4000, vram_mb=4000, backend="vulkan", quantization="Q4_K_M")
    runtime = VulkanLLMRuntime(name="qwen3", resource_profile=profile)
    
    # Healthy case
    mock_response_healthy = MagicMock()
    mock_response_healthy.status_code = 200
    with patch("requests.get", return_value=mock_response_healthy):
        status = runtime.health_check()
        assert status.healthy is True
        
    # Unhealthy case (status code)
    mock_response_unhealthy = MagicMock()
    mock_response_unhealthy.status_code = 503
    with patch("requests.get", return_value=mock_response_unhealthy):
        status = runtime.health_check()
        assert status.healthy is False

    # Unhealthy case (exception)
    with patch("requests.get", side_effect=requests.RequestException("Unreachable")):
        status = runtime.health_check()
        assert status.healthy is False
