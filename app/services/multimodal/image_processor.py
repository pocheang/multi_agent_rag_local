"""Image processing service for multi-modal RAG."""

import logging

from app.services.multimodal.models import ImageContent

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Index an image that ingestion has already read and described.

    It used to also extract images from a PDF, call GPT-4V and Claude directly,
    and run two OCR engines -- fourteen methods, none of which anything
    constructed a caller for. `ingest_paths` builds this and calls `index_image`,
    and the reading and describing happen in `app/ingestion/extraction/`, which
    is where the masking boundary is."""

    def index_image(self, image: ImageContent, collection_name: str = "image_descriptions") -> None:
        """Index image content in vector database.

        Synchronous: it awaits nothing, and its caller is document ingestion,
        which runs in a worker thread where an event loop must not be driven.

        Args:
            image: ImageContent with description
            collection_name: ChromaDB collection name
        """
        try:
            from app.retrievers.stores.vector import get_named_vector_store

            store = get_named_vector_store(collection_name)

            # Combine description and OCR text for indexing
            text_to_index = image.description
            if image.ocr_text:
                text_to_index += f"\n\nExtracted text: {image.ocr_text}"

            # Add to collection
            store.add_texts(
                ids=[image.image_id],
                texts=[text_to_index],
                metadatas=[
                    {
                        "doc_id": image.doc_id,
                        "document_id": image.document_id,
                        "tenant_id": image.tenant_id,
                        "owner_user_id": image.owner_user_id,
                        "visibility": image.visibility,
                        "version": image.version,
                        "page_number": image.page_number,
                        "image_id": image.image_id,
                        "artifact_uri": image.artifact_uri or "",
                        "source": image.metadata.get("source", image.artifact_uri or image.doc_id),
                        "type": "image",
                        "image_type": image.image_type,
                        "has_ocr": bool(image.ocr_text),
                        "width": image.metadata.get("width", 0),
                        "height": image.metadata.get("height", 0),
                    }
                ],
            )

            logger.info(f"Indexed image {image.image_id} in collection {collection_name}")

        except Exception:
            logger.exception(f"Error indexing image {image.image_id}")
            raise


def _image_media_type(extension: str) -> str:
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
    }.get(str(extension or "").lower(), "application/octet-stream")


def _image_extension(media_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/webp": "webp",
        "image/tiff": "tiff",
    }.get(str(media_type or "").lower(), "png")
