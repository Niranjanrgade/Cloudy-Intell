"""Vector store construction and RAG helper functions."""

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
    validator calls.
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
            results.append(f"[Document {i}]:\\n{content}\\n")

        return "\\n---\\n".join(results)
    except Exception as exc:
        return f"Error searching vector database: {exc}"
