# Ollama Cloud Documentation

Source: https://docs.ollama.com/cloud

## Cloud Models

Ollama's cloud models are a new kind of model in Ollama that can run without a powerful GPU. Instead, cloud models are automatically offloaded to Ollama's cloud service while offering the same capabilities as local models, making it possible to keep using your local tools while running larger models that wouldn't fit on a personal computer.

### Supported Models

For a list of supported models, see Ollama's [model library](https://ollama.com/search?c=cloud).

### Running Cloud Models

Ollama's cloud models require an account on [ollama.com](https://ollama.com/). To sign in or create an account, run:

```bash
ollama signin
```

To run a cloud model, open the terminal and run:

```bash
ollama run gpt-oss:120b-cloud
```

First, pull a cloud model so it can be accessed:

```bash
ollama pull gpt-oss:120b-cloud
```

#### Python

Install Ollama's Python library:

```bash
pip install ollama
```

Create and run a simple Python script:

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

#### JavaScript

Install Ollama's JavaScript library:

```bash
npm i ollama
```

Then use the library to run a cloud model:

```javascript
import { Ollama } from "ollama";

const ollama = new Ollama();

const response = await ollama.chat({
  model: "gpt-oss:120b-cloud",
  messages: [{ role: "user", content: "Explain quantum computing" }],
  stream: true,
});

for await (const part of response) {
  process.stdout.write(part.message.content);
}
```

#### cURL

Run the following cURL command:

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "gpt-oss:120b-cloud",
  "messages": [{
    "role": "user",
    "content": "Why is the sky blue?"
  }],
  "stream": false
}'
```

## Cloud API Access

Cloud models can also be accessed directly on ollama.com's API. In this mode, ollama.com acts as a remote Ollama host.

### Authentication

For direct access to ollama.com's API, first create an [API key](https://ollama.com/settings/keys). Then, set the `OLLAMA_API_KEY` environment variable to your API key.

```bash
export OLLAMA_API_KEY=your_api_key
```

### Listing Models

Models can be listed via:

```bash
curl https://ollama.com/api/tags
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

#### JavaScript

```javascript
import { Ollama } from "ollama";

const ollama = new Ollama({
  host: "https://ollama.com",
  headers: {
    Authorization: "Bearer " + process.env.OLLAMA_API_KEY,
  },
});

const response = await ollama.chat({
  model: "gpt-oss:120b",
  messages: [{ role: "user", content: "Explain quantum computing" }],
  stream: true,
});

for await (const part of response) {
  process.stdout.write(part.message.content);
}
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
