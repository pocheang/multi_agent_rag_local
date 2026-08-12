"""Re-index security documentation into the RAG system."""

from pathlib import Path
from app.services.documents.ingest import ingest_paths

def main():
    # Get all security markdown files
    security_dir = Path('data/docs/security')
    security_files = list(security_dir.glob('*.md'))

    print(f'Found {len(security_files)} security documents:')
    for f in sorted(security_files):
        print(f'  - {f.name}')

    print('\nRe-indexing security documents...')

    # Re-ingest without resetting vector store (merge with existing data)
    result = ingest_paths(security_files, reset_vector_store=False)

    print(f"\nResults:")
    print(f"  Files loaded: {result.get('loaded_documents', 0)}")
    print(f"  Chunks indexed: {result.get('chunks_indexed', 0)}")
    print(f"  Triplets written: {result.get('triplets_written', 0)}")

    # Verify indexing
    from app.retrievers.stores.corpus import read_corpus_records
    records = read_corpus_records()
    security_records = [r for r in records if 'security' in str(r.get('metadata', {}).get('source', '')).lower()]

    print(f"\nVerification:")
    print(f"  Total records in corpus: {len(records)}")
    print(f"  Security records: {len(security_records)}")

    # Show distribution
    sources = {}
    for r in security_records:
        source = r.get('metadata', {}).get('source', '')
        sources[source] = sources.get(source, 0) + 1

    print(f"\nChunk distribution:")
    for source, count in sorted(sources.items()):
        if source:
            filename = source.split('\\')[-1]
            print(f"  {filename:40s} {count:4d} chunks")

if __name__ == '__main__':
    main()
