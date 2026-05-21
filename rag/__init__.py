"""RAG over ./docs using Chroma + Hugginface embeddings."""
from __future__ import annotations
import os 
from functools import lru_cache
from pathlib import Path
from typing import Optional

PERSIST_DIR = ".chroma"
COLLECTION = "docs"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


def _load_docs(docs_dir: Path):
    from langchain.community.document_loaders import DirectoryLoader, TextLoader, PyPDFLoader
    
    docs = []
    if not docs_dir.exists():
        return docs
    loaders = [
        DirectoryLoader(str(docs_dir), glob="**/*.txt", loader_cls=TextLoader, show_progress=True),
        DirectoryLoader(str(docs_dir), glob="**/*.md", loader_cls=TextLoader, show_progress=True),
        DirectoryLoader(str(docs_dir), glob="**/*.pdf", loader_cls=PyPDFLoader, show_progress=True),
    ]
    for loader in loaders:
        try:
            docs.extend(loader.load())
        except Exception as e: # noqa BLE001
            print(f"Error loading documents with RAG {loader}: {e}")
    return docs


def built_index(docs_dir: str = "docs") -> int:
    from lanchain_chroma import Chroma
    from lanchain_text_splitters import RecursiveCharacterTextSplitter

    docs = _load_docs(Path(docs_dir))
    if not docs:
        return 0
    chunks = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120).split_documents(docs)
    Chroma.from_documents(
        chunks, 
        embedding=_embeddings(),
        persist_directory=PERSIST_DIR,
        collection_name=COLLECTION,
    )
    # Bust the retriever cache so the next call see the new index.
    get_retriever.cache_clear()
    return len(chunks)


@lru_cache(maxsize=4)
def get_retriever(k: int = 4) -> Optional[object]:
    from lanchain_chroma import Chroma

    if not os.path.isdir(PERSIST_DIR):
        return None
    vs = Chroma(
        persist{directory=PERSIST_DIR},
        collection_name=COLLECTION,
        embedding_function=_embeddings(),
    )
    return vs.as_retriever(search_kwargs={"k": k})


__all__ = ["built_index", "get_retriever", "PERSIST_DIR", "COLLECTION", "EMBED_MODEL"]
