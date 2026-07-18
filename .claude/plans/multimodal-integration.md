# Multimodal RAG System Integration Plan

## Executive Summary

This plan adds **comprehensive multimodal capabilities** to the existing RAG system, enabling it to process, index, and retrieve information from images, charts, tables, and text simultaneously. The integration follows the existing 4-tier agent architecture and maintains backward compatibility.

## Current State Analysis

### Existing Capabilities
- **Text Processing**: PDF (pypdf/docling), TXT, MD, CSV via `app/ingestion/loaders.py`
- **Image OCR**: Tesseract-based OCR for text extraction from images (`image_loader.py`)
- **Chart Extraction**: Vision-based chart extraction from PDFs (`pdf_chart_loader.py`)
- **Embeddings**: Text-only via BGE-M3 (Sentence-Transformers) or OpenAI text-embedding-3
- **Vector Store**: ChromaDB with text embeddings only
- **Vision Models**: GPT-4o/Claude Opus for chart captioning (config lines 121, 237-238)

### Gaps for Full Multimodality
1. **No unified image embeddings** - images processed via OCR only, not semantically indexed
2. **No multimodal retrieval** - cannot match visual content to textual queries
3. **No image-text fusion** - text and visual embeddings stored/retrieved separately
4. **No multimodal query support** - cannot query with images
5. **Limited visual reasoning** - chart extraction isolated, not integrated into agent reasoning

---

## Architecture Design

### Three-Tier Multimodal Integration

#### **Tier 1: Embedding & Storage Layer**
Add multimodal embedding models alongside text embeddings.

**Recommended Models:**
- **CLIP (OpenAI)** - Best text-image alignment, 512d embeddings
- **BLIP-2** - Strong visual understanding + text generation
- **SigLIP** - Improved over CLIP for batch processing

**Storage Strategy:**
```
ChromaDB Collections:
├── local_rag_collection (existing text)
├── local_rag_collection_vision (NEW: image embeddings)
└── local_rag_collection_multimodal (FUTURE: joint embeddings)
```

#### **Tier 2: Ingestion & Processing Layer**
Extend existing loaders to extract visual features.

**Processing Pipeline:**
```
Image/PDF → [Text Extraction] → Text Chunks
           ↓
           [Vision Embedding] → Vision Chunks
           ↓
           [Fusion] → Multimodal Chunks (text + image metadata)
```

#### **Tier 3: Retrieval & Agent Layer**
Extend retrieval agents to query both text and vision stores.

**Agent Extensions:**
- `EnhancedVectorRAGAgent` → Add vision retrieval path
- `HybridRetriever` → Fuse text + vision results
- `SynthesisAgent` → Cite image sources alongside text

---

## Implementation Plan

### Phase 1: Foundation (1-2 days)
**Goal:** Add multimodal embedding infrastructure

**Tasks:**
1. **Add CLIP embedding service** ([app/services/vision_embedding_service.py](app/services/vision_embedding_service.py))
   - Implement CLIP model loading (Hugging Face `openai/clip-vit-large-patch14`)
   - Add image preprocessing (resize, normalize)
   - Support batch embedding for performance

2. **Create vision vector store** ([app/retrievers/vision_vector_store.py](app/retrievers/vision_vector_store.py))
   - Initialize separate ChromaDB collection `local_rag_collection_vision`
   - Add `vision_similarity_search()` function
   - Implement source filtering (same security model as text store)

3. **Update configuration** ([app/core/config.py](app/core/config.py))
   - Add vision model settings:
     ```python
     vision_embed_model: str = "openai/clip-vit-large-patch14"
     vision_embed_backend: str = "local"  # local|openai
     vision_collection: str = "local_rag_collection_vision"
     enable_multimodal: bool = True
     multimodal_fusion_weight: float = 0.5  # text vs vision weight
     ```

**Files Created:**
- `app/services/vision_embedding_service.py`
- `app/retrievers/vision_vector_store.py`

**Files Modified:**
- `app/core/config.py`
- `app/core/models.py` (add `get_vision_embedding_model()`)

### Phase 2: Ingestion Extension (1 day)
**Goal:** Extract and index visual features during document ingestion

**Tasks:**
1. **Extend image loader** ([app/ingestion/loaders/image_loader.py](app/ingestion/loaders/image_loader.py))
   - Extract CLIP embeddings for images
   - Store embeddings + image metadata (path, caption, dimensions)
   - Generate captions using existing vision models (GPT-4o/Claude)

2. **Extend PDF chart loader** ([app/ingestion/loaders/pdf_chart_loader.py](app/ingestion/loaders/pdf_chart_loader.py))
   - Embed extracted charts with CLIP
   - Link charts to source text chunks (page number, parent chunk)

3. **Update ingest service** ([app/services/ingest_service.py](app/services/ingest_service.py))
   - Add vision embedding step after text chunking
   - Store vision records in `vision_vector_store`
   - Maintain bidirectional links: text_chunk ↔ image_chunk

**Files Modified:**
- `app/ingestion/loaders/image_loader.py`
- `app/ingestion/loaders/pdf_chart_loader.py`
- `app/services/ingest_service.py`

**Data Schema:**
```python
VisionRecord = {
    "id": "img_abc123",
    "image_path": "uploads/chart_p5.png",
    "embedding": [0.123, ...],  # 512d CLIP vector
    "caption": "Bar chart showing revenue growth",
    "metadata": {
        "source": "report.pdf",
        "page": 5,
        "linked_chunk_ids": ["chunk_xyz"],
        "image_type": "chart|photo|diagram",
        "dimensions": {"width": 800, "height": 600}
    }
}
```

### Phase 3: Multimodal Retrieval (1-2 days)
**Goal:** Enable hybrid text-vision retrieval

**Tasks:**
1. **Extend hybrid retriever** ([app/retrievers/hybrid_retriever.py](app/retrievers/hybrid_retriever.py))
   - Add `multimodal_search()` function
   - Implement late fusion: text_scores + vision_scores
   - Use weighted RRF: `score = w_text * rrf_text + w_vision * rrf_vision`

2. **Create multimodal reranker** ([app/retrievers/multimodal_reranker.py](app/retrievers/multimodal_reranker.py))
   - Use CLIP text-image similarity for cross-modal reranking
   - Boost results with high text-vision alignment

3. **Update EnhancedVectorRAGAgent** ([app/agents/enhanced_vector_rag_agent.py](app/agents/enhanced_vector_rag_agent.py))
   - Add `use_multimodal` parameter
   - Query both text and vision stores
   - Return fused results with image references

**Files Created:**
- `app/retrievers/multimodal_reranker.py`

**Files Modified:**
- `app/retrievers/hybrid_retriever.py`
- `app/agents/enhanced_vector_rag_agent.py`

**Retrieval Logic:**
```python
def multimodal_search(query: str, use_vision: bool = True):
    # Text retrieval (existing)
    text_results = hybrid_search(query)
    
    if not use_vision:
        return text_results
    
    # Vision retrieval (new)
    query_embedding = clip_encode_text(query)
    vision_results = vision_similarity_search(query_embedding)
    
    # Fusion
    fused = late_fusion_rrf(text_results, vision_results, k=60)
    reranked = multimodal_rerank(query, fused)
    return reranked
```

### Phase 4: Agent Integration (1 day)
**Goal:** Enable agents to reason about visual content

**Tasks:**
1. **Update SynthesisAgent** ([app/agents/synthesis_agent.py](app/agents/synthesis_agent.py))
   - Render image citations: `![chart](image_id:page)` in Markdown
   - Include image captions in context
   - Support multimodal answer formatting

2. **Update quality agents**
   - `RetrievalQualityAgent`: Score vision results relevance
   - `AnswerValidatorAgent`: Validate image citations

3. **Update router agent** ([app/agents/enhanced_router_agent.py](app/agents/enhanced_router_agent.py))
   - Add "multimodal" query intent classification
   - Route visual queries to vision-enabled retrieval

**Files Modified:**
- `app/agents/synthesis_agent.py`
- `app/agents/retrieval_quality_agent.py`
- `app/agents/answer_validator_agent.py`
- `app/agents/enhanced_router_agent.py`

### Phase 5: API & Frontend (1-2 days)
**Goal:** Expose multimodal features to users

**Tasks:**
1. **API endpoints** ([app/api/routes/](app/api/routes/))
   - `POST /api/query/multimodal` - Accept text + optional image queries
   - `GET /api/images/{image_id}` - Serve indexed images
   - Update `/api/documents/upload` to extract vision embeddings

2. **Frontend components** ([frontend/src/](frontend/src/))
   - Display inline images in answers
   - Support image upload in query composer
   - Show visual citations in DocumentsPanel

**Files Modified:**
- `app/api/routes/enhanced_query.py`
- `app/api/routes/documents.py`
- `frontend/src/pages/chat/components/MessageDisplay.tsx`
- `frontend/src/pages/chat/components/DocumentsPanel.tsx`

---

## Technical Recommendations

### Model Selection

| Model | Pros | Cons | Recommendation |
|-------|------|------|----------------|
| **CLIP (OpenAI)** | Best text-image alignment, fast, 512d | Limited to 77 token text input | ✅ **Primary choice** |
| **BLIP-2** | Strong captioning, flexible | Slower, 768d embeddings | Secondary option |
| **SigLIP** | Improved over CLIP, better batch processing | Newer, less tested | Future upgrade |

### Storage Strategy

**Option A: Separate Collections (Recommended)**
- Text in `local_rag_collection`
- Images in `local_rag_collection_vision`
- Linked via metadata `{"linked_image_ids": [...]}`

**Pros:** Clean separation, independent scaling, easier debugging  
**Cons:** Two retrieval passes required

**Option B: Unified Multimodal Collection**
- Store text + image embeddings together
- Use metadata to distinguish types

**Pros:** Single retrieval pass  
**Cons:** Complex filtering, embedding dimension mismatch (BGE-M3: 1024d vs CLIP: 512d)

### Fusion Strategies

**Early Fusion:** Concatenate text and image features before retrieval
- Requires joint embedding space (complex)

**Late Fusion (Recommended):** Retrieve separately, then merge scores
```python
final_score = w_text * text_relevance + w_vision * vision_relevance
```

**Cross-Attention Fusion:** Use transformer to fuse text-image features
- Most accurate but computationally expensive

---

## Performance Considerations

### Latency Impact
- **CLIP inference:** ~50ms per image (CPU), ~10ms (GPU)
- **Vision retrieval:** +100-200ms per query (parallel with text retrieval)
- **Mitigation:** Batch embedding, GPU acceleration, caching

### Storage Impact
- **Text embeddings:** 1024d × 4 bytes = 4KB per chunk
- **Vision embeddings:** 512d × 4 bytes = 2KB per image
- **Estimate:** 100 PDFs with 10 charts each = 1000 images × 2KB = 2MB

### Memory Requirements
- **CLIP model:** ~600MB RAM (CPU mode)
- **BGE-M3 (existing):** ~1.2GB RAM
- **Total:** ~2GB RAM for embedding services

---

## Testing Strategy

### Unit Tests
- `tests/services/test_vision_embedding_service.py`
- `tests/retrievers/test_vision_vector_store.py`
- `tests/retrievers/test_multimodal_reranker.py`

### Integration Tests
- `tests/integration/test_multimodal_ingestion.py`
- `tests/integration/test_multimodal_retrieval.py`
- `tests/integration/test_end_to_end_multimodal.py`

### Evaluation Metrics
- **Text-to-Image Retrieval Precision@5:** >0.75
- **Image-to-Image Retrieval Precision@5:** >0.85
- **Multimodal Answer Completeness:** Include relevant images in >80% of visual queries

---

## Security & Privacy

### Image Access Control
- Apply same source filtering as text: `filter={"source": {"$in": allowed_sources}}`
- Store images in user-isolated directories: `uploads/{user_id}/`
- Redact PII from images before embedding (use existing `outbound_redaction.py`)

### Vision Model Safety
- Detect and filter sensitive content (use existing `people_detection.py`)
- Block embedding of faces if `PEOPLE_DETECTION_ENABLED=True`

---

## Migration & Backward Compatibility

### Existing Data
- **No reingestion required** for text-only use cases
- Vision features added incrementally on new uploads
- Add `python scripts/reindex_vision.py` to batch-process existing documents

### Feature Flags
```python
# .env
ENABLE_MULTIMODAL=True  # Master switch
VISION_EMBED_BACKEND=local  # local|openai
MULTIMODAL_FUSION_WEIGHT=0.5  # 0.0 = text-only, 1.0 = vision-only
```

### API Versioning
- `/api/v1/query` - Text-only (existing, unchanged)
- `/api/v1/query?multimodal=true` - Opt-in multimodal
- `/api/v2/query` - Multimodal by default (future)

---

## Rollout Plan

### Week 1: Foundation + Ingestion
- Days 1-2: Phase 1 (embedding infrastructure)
- Days 3-4: Phase 2 (ingestion extension)
- Day 5: Testing + fixes

### Week 2: Retrieval + Integration
- Days 1-2: Phase 3 (multimodal retrieval)
- Day 3: Phase 4 (agent integration)
- Days 4-5: Phase 5 (API + frontend)

### Week 3: Testing + Optimization
- Days 1-2: Integration testing
- Day 3: Performance tuning
- Days 4-5: Documentation + demo

---

## Success Criteria

✅ **Functional:**
- Users can upload images and retrieve them via text queries
- Charts in PDFs automatically indexed and retrievable
- Answers cite both text and image sources

✅ **Quality:**
- Multimodal retrieval precision@5 > 0.75
- No hallucinated image references (100% citation accuracy)
- Visual answers preferred when available (user feedback)

✅ **Performance:**
- P95 latency increase < 500ms vs text-only
- Throughput > 80% of text-only baseline

✅ **Production:**
- Zero breaking changes to existing text-only workflows
- Feature flag allows instant rollback
- Monitoring dashboards show multimodal metrics

---

## Open Questions for User

1. **Model Selection:** Use local CLIP (free, slower) or OpenAI CLIP API (paid, faster)?
2. **Fusion Weight:** Default 0.5 (equal text/vision) or bias toward text (0.7/0.3)?
3. **Reindexing:** Batch-reindex existing documents immediately or on-demand?
4. **Frontend Priority:** Show images inline in answers or as sidebar thumbnails?
5. **GPU Support:** Deploy with GPU acceleration for CLIP inference?

---

## Alternative Approaches Considered

### Approach A: Vision-Language Models (VLMs) Only
**Rejected:** VLMs (GPT-4o, Claude Opus) too slow/expensive for real-time retrieval. Better suited for synthesis stage.

### Approach B: Text-Only with Image Captioning
**Rejected:** Captions lose visual semantics. CLIP embeddings preserve spatial/visual features.

### Approach C: Unified Embedding Model (ImageBind)
**Rejected:** ImageBind experimental, large model size (5GB+), difficult to fine-tune.

---

## Key Dependencies

### Python Packages (to add to requirements.txt)
```
transformers>=4.35.0
torch>=2.0.0
pillow>=10.0.0
clip-by-openai>=1.0  # or openai/clip-vit-large-patch14 via transformers
```

### Model Downloads (Hugging Face)
- `openai/clip-vit-large-patch14` (~900MB)
- Alternative: `openai/clip-vit-base-patch32` (~350MB, faster but less accurate)

---

## References

- **CLIP Paper:** https://arxiv.org/abs/2103.00020
- **LangChain Multimodal RAG:** https://python.langchain.com/docs/how_to/multi_modal_rag/
- **ChromaDB Multimodal:** https://docs.trychroma.com/guides/multimodal
- **BGE-M3:** https://huggingface.co/BAAI/bge-m3
- **Multimodal RAG Best Practices:** https://blog.langchain.dev/semi-structured-multi-modal-rag/

---

## Appendix: Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     User Query (Text/Image)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │   Router Agent       │
              │  (Query Analysis)    │
              └──────────┬───────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────┐
│  Text       │  │   Vision     │  │   Hybrid     │
│  Retrieval  │  │  Retrieval   │  │  Retrieval   │
└──────┬──────┘  └──────┬───────┘  └──────┬───────┘
       │                │                  │
       │    ┌───────────┴─────────┐       │
       │    │                     │       │
       ▼    ▼                     ▼       ▼
┌────────────────────────────────────────────┐
│       Multimodal Fusion & Reranking        │
│   (RRF + CLIP cross-modal similarity)      │
└────────────────┬───────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  Quality Check │
        │   (4-Layer)    │
        └────────┬───────┘
                 │
                 ▼
        ┌────────────────┐
        │   Synthesis    │
        │  (Citations)   │
        └────────┬───────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│   Answer + Text Citations + Image Links    │
└────────────────────────────────────────────┘
```

---

**Next Steps:** Await user approval, then execute Phase 1 - Foundation.
