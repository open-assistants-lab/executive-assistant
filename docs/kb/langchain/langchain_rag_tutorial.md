# Build a RAG Agent with LangChain

One of the most powerful applications enabled by LLMs is sophisticated question-answering (Q&A) chatbots. These applications use a technique known as Retrieval Augmented Generation, or RAG.

## Concepts

We will cover the following concepts:

* **Indexing**: a pipeline for ingesting data from a source and indexing it. This usually happens in a separate process.
* **Retrieval and generation**: the actual RAG process, which takes the user query at run time and retrieves the relevant data from the index, then passes that to the model.

## Indexing Pipeline

Indexing commonly works as follows:

1. **Load**: First we need to load our data using Document Loaders.
2. **Split**: Text splitters break large Documents into smaller chunks for indexing and model context window management.
3. **Store**: We need a VectorStore and Embeddings model to store and index our splits for search.

### Loading Documents

Use DocumentLoaders to load data from sources. For web content:

```python
import bs4
from langchain_community.document_loaders import WebBaseLoader

bs4_strainer = bs4.SoupStrainer(class_=("post-title", "post-header", "post-content"))
loader = WebBaseLoader(
    web_paths=("https://lilianweng.github.io/posts/2023-06-23-agent/",),
    bs_kwargs={"parse_only": bs4_strainer},
)
docs = loader.load()
```

### Splitting Documents

Use RecursiveCharacterTextSplitter for generic text:

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,  # chunk size (characters)
    chunk_overlap=200,  # chunk overlap (characters)
    add_start_index=True,  # track index in original document
)
all_splits = text_splitter.split_documents(docs)
```

### Storing Documents

Embed and store document splits using a vector store:

```python
document_ids = vector_store.add_documents(documents=all_splits)
```

## Retrieval and Generation

### RAG Agents

Create a retrieval tool and wrap it in an agent:

```python
from langchain.tools import tool

@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    """Retrieve information to help answer a query."""
    retrieved_docs = vector_store.similarity_search(query, k=2)
    serialized = "\n\n".join(
        (f"Source: {doc.metadata}\nContent: {doc.page_content}")
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs

tools = [retrieve_context]
agent = create_agent(model, tools, system_prompt="You have access to a tool that retrieves context from a blog post. Use the tool to help answer user queries.")
```

### RAG Chains

For simple queries, use a two-step chain:

```python
from langchain.agents.middleware import dynamic_prompt, ModelRequest

@dynamic_prompt
def prompt_with_context(request: ModelRequest) -> str:
    """Inject context into state messages."""
    last_query = request.state["messages"][-1].text
    retrieved_docs = vector_store.similarity_search(last_query)

    docs_content = "\n\n".join(doc.page_content for doc in retrieved_docs)

    system_message = (
        "You are a helpful assistant. Use the following context in your response:"
        f"\n\n{docs_content}"
    )

    return system_message

agent = create_agent(model, tools=[], middleware=[prompt_with_context])
```

## Trade-offs

| RAG Agents | RAG Chains |
|------------|------------|
| Search only when needed | Always search |
| Contextual search queries | Single inference call |
| Multiple searches allowed | Reduced latency |
| Two inference calls | Less flexible |

## Next Steps

* Stream tokens and other information for responsive user experiences
* Add conversational memory for multi-turn interactions
* Add long-term memory across conversations
* Add structured responses
* Deploy with LangSmith Deployment
