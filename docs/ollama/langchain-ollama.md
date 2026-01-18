# ChatOllama - LangChain Integration

Source: https://docs.langchain.com/oss/python/integrations/chat/ollama

## Overview

Ollama allows you to run open-source Large Language Models (LLMs), such as `gpt-oss`, locally.

Ollama bundles model weights, configuration, and data into a single package, defined by a Modelfile. It optimizes setup and configuration details, including GPU usage.

For a complete list of supported models and model variants, see the Ollama model library.

## Setup

### Installation

Install LangChain Ollama integration:

```bash
pip install -qU langchain-ollama
```

### Instantiation

```python
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model="llama3.1",
    temperature=0,
    # other params...
)
```

## Invocation

```python
messages = [
    ("system", "You are a helpful assistant that translates English to French. Translate the user sentence."),
    ("human", "I love programming."),
]
ai_msg = llm.invoke(messages)
ai_msg
```

## Cloud API Access

### Authentication

For direct access to ollama.com's API, first create an [API key](https://ollama.com/settings/keys). Then, set the `OLLAMA_API_KEY` environment variable.

```bash
export OLLAMA_API_KEY=your_api_key
```

### Generating a Response via API

#### Python

```python
import os
from ollama import Client

client = Client(
    host="https://ollama.com",
    headers={'Authorization': 'Bearer ' + os.environ.get('OLLAMA_API_KEY')}
)

messages = [
    {
        'role': 'user',
        'content': 'Why is the sky blue?',
    },
]

for part in client.chat('gpt-oss:120b', messages=messages, stream=True):
    print(part['message']['content'], end='', flush=True)
```

#### cURL

```bash
curl https://ollama.com/api/chat \
  -H "Authorization: Bearer $OLLAMA_API_KEY" \
  -d '{
    "model": "gpt-oss:120b",
    "messages": [{
      "role": "user",
      "content": "Why is the sky blue?"
    }],
    "stream": false
  }'
```

## Ollama Cloud

Ollama's cloud models run without a powerful GPU - they are offloaded to Ollama's cloud service.

### Running Cloud Models

First, pull a cloud model:

```bash
ollama pull gpt-oss:120b-cloud
```

Then use via:

```bash
ollama run gpt-oss:120b-cloud
```

### Using Ollama Cloud

1. Create an account on [ollama.com](https://ollama.com/)
2. Run `ollama signin`
3. Install [Ollama's Python library](https://github.com/ollama/ollama-python):

```bash
pip install ollama
```

4. Create and run:

```python
from ollama import Client

client = Client()

messages = [
    {
        'role': 'user',
        'content': 'Why is the sky blue?',
    },
]

for part in client.chat('gpt-oss:120b-cloud', messages=messages, stream=True):
    print(part['message']['content'], end='', flush=True)
```
