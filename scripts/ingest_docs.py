#!/usr/bin/env python
"""Ingest seed docs into PGVector"""
import pathlib
from packages.rag.vectorstore import get_vectorstore, get_embeddings

def main():
    vs = get_vectorstore()
    if not vs or not hasattr(vs, "add_texts"):
        print("Vectorstore is FAISS mock - skipping persistent ingest")
        return
    texts = []
    for p in pathlib.Path("data/seed").rglob("*.md"):
        texts.append(p.read_text())
    if texts:
        vs.add_texts(texts)
        print(f"Ingested {len(texts)} docs")
    else:
        print("No docs found")

if __name__ == "__main__":
    main()
