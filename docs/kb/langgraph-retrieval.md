# LangGraph Retrieval (RAG) - Knowledge Base

## Overview

Retrieval Augmented Generation (RAG) enhances LLM responses by fetching relevant external context. LangGraph provides flexible patterns for building retrieval agents that can decide when to retrieve and how to use retrieved information.

## Basic RAG Setup

### Vector Store Setup

```python
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Load documents
urls = ["https://example.com/doc1", "https://example.com/doc2"]
docs = [WebBaseLoader(url).load() for url in urls]

# Split documents
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
splits = text_splitter.split_documents(docs)

# Create vector store
vectorstore = InMemoryVectorStore.from_documents(
    documents=splits,
    embedding=OpenAIEmbeddings()
)

# Create retriever
retriever = vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 4}
)
```

### Retriever Tool

```python
from langchain.tools import tool

@tool
def retrieve_documents(query: str) -> str:
    """Search and return relevant document content."""
    docs = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])

# Use in agent
agent = create_agent(
    model="gpt-4o",
    tools=[retrieve_documents]
)
```

## Agentic RAG (Self-Deciding Retrieval)

The agent decides **when** to retrieve:

```python
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode, tools_condition

# Create retriever tool
retriever_tool = retrieve_documents

# Agent node that decides retrieval
def agent_node(state: MessagesState):
    """LLM decides whether to retrieve or respond directly."""
    response = model.bind_tools([retriever_tool]).invoke(state["messages"])
    return {"messages": [response]}

# Build graph
workflow = StateGraph(MessagesState)
workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode([retriever_tool]))

workflow.add_edge(START, "agent")

# Route: if tool called -> retrieve, else -> end
workflow.add_conditional_edges(
    "agent",
    tools_condition,
    {"tools": "tools", END: END}
)

workflow.add_edge("tools", "agent")

graph = workflow.compile()
```

## Advanced RAG Patterns

### RAG with Document Grading

Filter retrieved documents by relevance:

```python
from pydantic import BaseModel, Field

class DocumentGrade(BaseModel):
    """Grade document relevance."""
    binary_score: str = Field(description="'yes' if relevant, 'no' if not")

def grade_documents(state: MessagesState) -> Literal["generate", "rewrite"]:
    """Grade retrieved documents for relevance."""
    question = state["messages"][0].content
    docs = state["messages"][-1].content

    grader = model.with_structured_output(DocumentGrade)

    grade = grader.invoke(f"""
    Question: {question}
    Document: {docs}

    Is this document relevant?
    """)

    if grade.binary_score == "yes":
        return "generate"
    return "rewrite"  # Rewrite query and try again
```

### Query Rewriting

Improve retrieval with better queries:

```python
def rewrite_query_node(state: MessagesState):
    """Rewrite query for better retrieval."""
    original = state["messages"][0].content

    rewritten = model.invoke(f"""
    Improve this search query for document retrieval:
    "{original}"

    Return only the improved query.
    """)

    return {"messages": [HumanMessage(content=rewritten.content)]}
```

### Hybrid Retrieval

Combine multiple retrieval strategies:

```python
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever

# Semantic retriever
semantic_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

# Keyword retriever
bm25_retriever = BM25Retriever.from_documents(splits)

# Ensemble (combines both)
ensemble_retriever = EnsembleRetriever(
    retrievers=[semantic_retriever, bm25_retriever],
    weights=[0.7, 0.3]  # Weight semantic higher
)

@tool
def hybrid_retrieve(query: str) -> str:
    """Retrieve using hybrid semantic + keyword search."""
    docs = ensemble_retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])
```

### Parent Document Retrieval

Retrieve small chunks but return larger context:

```python
from langchain.retrievers import ParentDocumentRetriever
from langchain.storage import InMemoryStore

# Parent splitter (large chunks)
parent_splitter = RecursiveCharacterTextSplitter(chunk_size=4000)

# Child splitter (small chunks for embedding)
child_splitter = RecursiveCharacterTextSplitter(chunk_size=500)

# Vector store for children
vectorstore = InMemoryVectorStore(embedding=OpenAIEmbeddings())

# Store for parents
store = InMemoryStore()

# Create parent document retriever
parent_retriever = ParentDocumentRetriever(
    vectorstore=vectorstore,
    docstore=store,
    child_splitter=child_splitter,
    parent_splitter=parent_splitter
)

# Add documents
parent_retriever.add_documents(docs)

@tool
def retrieve_with_context(query: str) -> str:
    """Retrieve small chunks but return large context."""
    docs = parent_retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])
```

### Self-Querying

Let the agent construct metadata filters:

```python
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever

metadata_fields = [
    AttributeInfo(name="category", description="Document category", type="string"),
    AttributeInfo(name="date", description="Publication date", type="string"),
    AttributeInfo(name="author", description="Document author", type="string"),
]

self_query_retriever = SelfQueryRetriever.from_llm(
    llm=model,
    vectorstore=vectorstore,
    document_contents="Technical documentation",
    metadata_field_info=metadata_fields
)

@tool
def smart_retrieve(query: str) -> str:
    """Retrieve with automatic metadata filtering."""
    docs = self_query_retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])
```

## RAG with LangGraph Store

Cross-thread persistent retrieval:

```python
from langgraph.store import BaseStore

def retrieve_with_memory(state: MessagesState, config: dict, store: BaseStore):
    """Retrieve from persistent memory store."""
    query = state["messages"][-1].content

    # Search stored documents
    results = store.search(
        namespace=["documents"],
        query=query,
        limit=5
    )

    context = "\n".join(r.value for r in results)

    return {
        "messages": [SystemMessage(content=f"Context: {context}")]
    }
```

## Retrieval Evaluation

### Relevance Scoring

```python
def relevance_score(query: str, document: str) -> float:
    """Score retrieval relevance."""
    scorer = model.with_structured_output(
        lambda: float
    )
    return scorer.invoke(f"""
    Rate relevance (0-1):
    Query: {query}
    Document: {document}
    """)
```

### Retrieval Testing

```python
test_cases = [
    {"query": "How to install?", "expected_keywords": ["pip", "install"]},
    {"query": "API usage", "expected_keywords": ["function", "class"]},
]

def test_retrieval(retriever):
    """Test retrieval quality."""
    for case in test_cases:
        docs = retriever.invoke(case["query"])
        content = " ".join([d.page_content for d in docs])

        for keyword in case["expected_keywords"]:
            assert keyword in content, f"Missing '{keyword}' in retrieval"
```

## Best Practices

1. **Chunk strategically**: Match chunk size to typical queries
2. **Hybrid search**: Combine semantic + keyword for best results
3. **Re-rank results**: Use LLM to re-rank top retrievals
4. **Monitor retrieval**: Track retrieval quality metrics
5. **Update embeddings**: Refresh when documents change

## References

- [Agentic RAG Tutorial](https://docs.langchain.com/oss/python/langgraph/agentic-rag)
- [Retrieval Documentation](https://docs.langchain.com/oss/python/langchain/retrieval)
- [Vector Store Integrations](https://docs.langchain.com/oss/python/integrations/vectorstores/)
