"""Vector store construction and RAG helper functions.

This module handles the ChromaDB vector store used for Retrieval-Augmented
Generation (RAG).  Each cloud provider (AWS, Azure) has its own ChromaDB
collection containing pre-embedded official documentation.  Domain validators
use the ``rag_search_function`` to retrieve relevant documentation snippets
that are injected into validation prompts for fact-checking.

The embedding model (Ollama-based ``nomic-embed-text``) must be running locally
for vector store queries to work.  The ChromaDB data is persisted on disk in
the directories specified by ``AppSettings.providers_aws_vector_path`` and
``providers_azure_vector_path``.
"""

from langchain_chroma import Chroma
from langchain_ollama.embeddings import OllamaEmbeddings

from cloudy_intell.config.settings import AppSettings


def create_vector_store(settings: AppSettings, provider: str = "aws") -> Chroma:
    """Create a cloud-documentation vector store instance.

    The path and collection name are resolved from provider-scoped settings so
    AWS and Azure can each have their own knowledge base.
    """

    embeddings = OllamaEmbeddings(model=settings.embedding_model)
    return Chroma(
        collection_name=settings.collection_name_for(provider),
        persist_directory=settings.vector_path_for(provider),
        embedding_function=embeddings,
    )


def rag_search_function(query: str, vector_store: Chroma, k: int = 5) -> str:
    """Search vector store and return bounded, formatted snippets.

    Snippet truncation is intentionally conservative to prevent prompt bloat in
    validator calls.  Each document snippet is capped at 1000 characters and
    up to ``k`` (default 5) similar documents are returned.

    Args:
        query: Natural language query to search for.
        vector_store: ChromaDB instance to search against.
        k: Number of top similar documents to retrieve.

    Returns:
        Formatted string of numbered document snippets separated by ``---``,
        or an error message if the search fails.
    """

    try:
        similar_docs = vector_store.similarity_search(query, k=k)
        if not similar_docs:
            return "No relevant documentation found in the vector database."

        results = []
        max_snippet_length = 1000
        for i, doc in enumerate(similar_docs, 1):
            content = doc.page_content.strip()
            if len(content) > max_snippet_length:
                content = content[:max_snippet_length] + "... [truncated]"
            results.append(f"[Document {i}]:\n{content}\n")

        return "\n---\n".join(results)
    except Exception as exc:
        return f"Error searching vector database: {exc}"
