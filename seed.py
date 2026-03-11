from app.db.session import Base, engine, SessionLocal
from app.models import SOP, Log, SOPChunk, LogChunk
from app.services.embeddings import embed_text
from app.services.faiss_store import add_vector
from app.services.chunking import chunk_text
from app.seed.seed_data import SOP_SAMPLES, LOG_SAMPLES


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(SOP).count() == 0:
            for title, content in SOP_SAMPLES:
                emb = embed_text(content)
                sop = SOP(title=title, content=content, embedding_vector=emb)
                db.add(sop)
                db.commit()
                db.refresh(sop)
                add_vector("sop", emb, sop.id)

                for idx, chunk in enumerate(chunk_text(content)):
                    c_emb = embed_text(chunk)
                    c = SOPChunk(sop_id=sop.id, chunk_index=idx, content=chunk, embedding_vector=c_emb)
                    db.add(c)
                    db.commit()
                    db.refresh(c)
                    add_vector("sop_chunk", c_emb, c.id)

        if db.query(Log).count() == 0:
            for title, content in LOG_SAMPLES:
                emb = embed_text(content)
                log = Log(title=title, content=content, embedding_vector=emb)
                db.add(log)
                db.commit()
                db.refresh(log)
                add_vector("log", emb, log.id)

                for idx, chunk in enumerate(chunk_text(content)):
                    c_emb = embed_text(chunk)
                    c = LogChunk(log_id=log.id, chunk_index=idx, content=chunk, embedding_vector=c_emb)
                    db.add(c)
                    db.commit()
                    db.refresh(c)
                    add_vector("log_chunk", c_emb, c.id)
    finally:
        db.close()

if __name__ == "__main__":
    run()