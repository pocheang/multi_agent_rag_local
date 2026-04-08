from app.core.config import get_settings
from app.services.ingest_service import ingest_docs_dir


def main():
    settings = get_settings()
    result = ingest_docs_dir(settings.docs_path, reset_vector_store=True)
    if not result.get("loaded_documents"):
        print(f"[WARN] no docs found in {settings.docs_path}")
        return

    print(f"[OK] loaded documents: {result['loaded_documents']}")
    print(f"[OK] chunks indexed: {result['chunks_indexed']}")
    print(f"[OK] corpus records updated -> {settings.corpus_path}")
    print(f"[OK] triplets written: {result['triplets_written']}")


if __name__ == "__main__":
    main()
