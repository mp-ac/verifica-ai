"""Serialization helpers for image-authenticity collections."""

from collections.abc import Iterable

from image_authenticity.schemas import ImageAuthenticityAnalysis


def serialize_image_authenticity_analyses(
    analyses: Iterable[ImageAuthenticityAnalysis | dict],
) -> list[dict]:
    """Validate, order and serialize assessments for public contracts."""
    validated = [
        ImageAuthenticityAnalysis.model_validate(analysis)
        for analysis in analyses
    ]
    return [
        analysis.model_dump()
        for analysis in sorted(
            validated,
            key=lambda item: item.attachment_index,
        )
    ]
