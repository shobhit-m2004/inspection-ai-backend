import os
from typing import List, Tuple, Optional
import faiss
import numpy as np

from app.services.embeddings import EMBEDDING_DIM

DATA_DIR = os.getenv("FAISS_DIR", "./app/data")
INDEX_PATHS = {
    "sop": os.path.join(DATA_DIR, "sops.index"),
    "log": os.path.join(DATA_DIR, "logs.index"),
    "sop_chunk": os.path.join(DATA_DIR, "sop_chunks.index"),
    "log_chunk": os.path.join(DATA_DIR, "log_chunks.index"),
}


def _ensure_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_or_create(path: str) -> faiss.Index:
    _ensure_dir()
    if os.path.exists(path):
        return faiss.read_index(path)
    index = faiss.IndexIDMap2(faiss.IndexFlatIP(EMBEDDING_DIM))
    faiss.write_index(index, path)
    return index


def _save(index: faiss.Index, path: str) -> None:
    faiss.write_index(index, path)


def add_vector(kind: str, vector: List[float], item_id: int) -> None:
    path = INDEX_PATHS[kind]
    index = _load_or_create(path)
    vec = np.array([vector], dtype="float32")
    faiss.normalize_L2(vec)
    index.add_with_ids(vec, np.array([item_id], dtype="int64"))
    _save(index, path)


def remove_vector(kind: str, item_id: int) -> bool:
    """
    Remove a vector from the FAISS index by item ID.
    
    Args:
        kind: Type of index ("sop", "log", "sop_chunk", "log_chunk")
        item_id: ID of the item to remove
        
    Returns:
        True if removed, False if not found
    """
    path = INDEX_PATHS[kind]
    if not os.path.exists(path):
        return False
    
    index = _load_or_create(path)
    
    # Check if the ID exists by converting id_map to list
    try:
        id_list = list(index.id_map)
        if item_id not in id_list:
            return False
    except Exception:
        # If id_map is empty or inaccessible, try to remove anyway
        pass
    
    # Remove the vector
    try:
        index.remove_ids(np.array([item_id], dtype="int64"))
        _save(index, path)
        return True
    except Exception:
        # Vector removal failed (might not exist)
        return False


def search(kind: str, vector: List[float], top_k: int = 5) -> List[Tuple[int, float]]:
    path = INDEX_PATHS[kind]
    if not os.path.exists(path):
        return []
    index = faiss.read_index(path)
    vec = np.array([vector], dtype="float32")
    faiss.normalize_L2(vec)
    scores, ids = index.search(vec, top_k)
    results = []
    for item_id, score in zip(ids[0].tolist(), scores[0].tolist()):
        if item_id == -1:
            continue
        results.append((item_id, float(score)))
    return results