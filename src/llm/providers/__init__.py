# Import providers with error handling for optional dependencies
try:
    from src.llm.providers.anthropic import AnthropicProvider
except ImportError:
    AnthropicProvider = None  # type: ignore

try:
    from src.llm.providers.azure import AzureProvider
except ImportError:
    AzureProvider = None  # type: ignore

try:
    from src.llm.providers.cohere import CohereProvider
except ImportError:
    CohereProvider = None  # type: ignore

try:
    from src.llm.providers.deepseek import DeepSeekProvider
except ImportError:
    DeepSeekProvider = None  # type: ignore

try:
    from src.llm.providers.fireworks import FireworksProvider
except ImportError:
    FireworksProvider = None  # type: ignore

try:
    from src.llm.providers.google import GoogleProvider
except ImportError:
    GoogleProvider = None  # type: ignore

try:
    from src.llm.providers.groq import GroqProvider
except ImportError:
    GroqProvider = None  # type: ignore

try:
    from src.llm.providers.huggingface import HuggingFaceProvider
except ImportError:
    HuggingFaceProvider = None  # type: ignore

try:
    from src.llm.providers.minimax import MinimaxProvider
except ImportError:
    MinimaxProvider = None  # type: ignore

try:
    from src.llm.providers.mistral import MistralProvider
except ImportError:
    MistralProvider = None  # type: ignore

try:
    from src.llm.providers.ollama import OllamaProvider
except ImportError:
    OllamaProvider = None  # type: ignore

try:
    from src.llm.providers.openai import OpenAIProvider
except ImportError:
    OpenAIProvider = None  # type: ignore

try:
    from src.llm.providers.openrouter import OpenRouterProvider
except ImportError:
    OpenRouterProvider = None  # type: ignore

try:
    from src.llm.providers.qwen import QwenProvider
except ImportError:
    QwenProvider = None  # type: ignore

try:
    from src.llm.providers.together import TogetherProvider
except ImportError:
    TogetherProvider = None  # type: ignore

try:
    from src.llm.providers.xai import XAIProvider
except ImportError:
    XAIProvider = None  # type: ignore

try:
    from src.llm.providers.zhipuai import ZhipuAIProvider
except ImportError:
    ZhipuAIProvider = None  # type: ignore

__all__ = [
    "AnthropicProvider",
    "AzureProvider",
    "CohereProvider",
    "DeepSeekProvider",
    "FireworksProvider",
    "GoogleProvider",
    "GroqProvider",
    "HuggingFaceProvider",
    "MinimaxProvider",
    "MistralProvider",
    "OllamaProvider",
    "OpenAIProvider",
    "OpenRouterProvider",
    "QwenProvider",
    "TogetherProvider",
    "XAIProvider",
    "ZhipuAIProvider",
]
