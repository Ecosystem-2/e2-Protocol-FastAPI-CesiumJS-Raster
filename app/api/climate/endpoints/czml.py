"""CZML export endpoints for polygon selections."""

from __future__ import annotations

import json
from typing import Optional, List

from fastapi import APIRouter, Form, HTTPException, Path, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from app.climate_indices import CZMLExportOptions, CZMLRecord, SelectionRepository, CZMLRepository
from app.climate_indices.czml_generate import CZMLExportService
from app.commons.colours import list_available_colourmaps, get_colourmap_categories
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


# %% ============================================================================
# Response Models
# ============================================================================


class CZMLExportResponse(BaseModel):
    """Response model for CZML export."""

    model_config = ConfigDict(populate_by_name=True)

    czml_id: str = Field(..., alias="czmlID")
    selection_ref: str = Field(..., alias="selectionRef")  # MongoDB ObjectId of the source selection
    index_type: str = Field(..., alias="indexType")
    visualisation_type: str = Field(..., alias="visualisationType")
    packet_count: int = Field(..., alias="packetCount")
    replaced: bool
    czml_document: List[dict] = Field(..., alias="czmlDocument")


class ColourmapListResponse(BaseModel):
    """Response model for colourmap listing."""
    colourmaps: List[str]
    count: int


class ColourmapCategoriesResponse(BaseModel):
    """Response model for categorised colourmaps."""
    categories: dict


# %% ============================================================================
# Colourmap Endpoints
# ============================================================================


@router.get(
    "/colourmaps",
    response_model=ColourmapListResponse,
    summary="List available colourmaps",
    description="Get all Matplotlib colourmaps available for CZML visualisation."
)
async def list_colourmaps(
    category: Optional[str] = Query(
        None,
        description="Filter by category: perceptually_uniform, sequential, diverging, etc."
    )
) -> ColourmapListResponse:
    """List all available Matplotlib colourmaps."""
    try:
        colourmaps = list_available_colourmaps(category)
        return ColourmapListResponse(colourmaps=colourmaps, count=len(colourmaps))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc


@router.get(
    "/colourmaps/categories",
    response_model=ColourmapCategoriesResponse,
    summary="Get colourmap categories",
    description="Get colourmaps organised by category."
)
async def get_colourmaps_by_category() -> ColourmapCategoriesResponse:
    """Get colourmaps organised by category."""
    categories = get_colourmap_categories()
    return ColourmapCategoriesResponse(categories=categories)


# %% ============================================================================
# CZML Export Endpoints
# ============================================================================


@router.post(
    "/selections/{id}/export-czml",
    response_model=CZMLExportResponse,
    summary="Export selection as CZML",
    description="Generate CZML visualisation and save to database."
)
async def export_selection_czml(
    id: str = Path(..., description="MongoDB ObjectId of the selection"),
    index_type: str = Form(..., alias="indexType", description="Climate index type (ppet, wbgt, etc.)"),
    visualisation_type: str = Form("polygon", alias="visualisationType", description="bar or polygon"),
    colourmap_name: str = Form("viridis", alias="colourmapName", description="Matplotlib colourmap name"),
    scale_min: Optional[float] = Form(None, alias="scaleMin"),
    scale_max: Optional[float] = Form(None, alias="scaleMax"),
    value_field: str = Form("mean", alias="valueField", description="mean, min, max, median, or std"),
    bar_height_multiplier: float = Form(10000.0, alias="barHeightMultiplier", gt=0),
    polygon_height_multiplier: float = Form(1000.0, alias="polygonHeightMultiplier", gt=0),
    polygon_fill_opacity: float = Form(0.7, alias="polygonFillOpacity", ge=0.0, le=1.0),
    polygon_outline: bool = Form(True, alias="polygonOutline"),
    show_labels: bool = Form(True, alias="showLabels"),
    interpolation_mode: str = Form("step", alias="interpolationMode", description="step or interpolation"),
    save_to_db: bool = Form(True, alias="saveToDb", description="Save CZML to database"),
    czml_id: Optional[str] = Form(None, alias="czmlID", description="Frontend-generated UUID for cross-system reference"),
    user_id: Optional[str] = Form(None, alias="userID", description="Owner user UUID for access control"),
    project_id: Optional[str] = Form(None, alias="projectID", description="Project UUID for grouping CZML documents"),
) -> CZMLExportResponse:
    """
    Export selection as CZML for Cesium visualisation.

    Uses `commons/colours.py` for colourmap rendering.
    Saves generated CZML to MongoDB czml_documents collection.
    
    The indexType parameter filters to export only one climate index
    (e.g., ppet or wbgt) to avoid overlapping polygons.
    """
    # Fetch selection
    selection_repo = SelectionRepository()
    selection = selection_repo.get_selection(id)

    if not selection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Selection not found: {id}"
        )

    # Build export options
    try:
        options = CZMLExportOptions(
            visualisation_type=visualisation_type,  # type: ignore
            colourmap_name=colourmap_name,
            scale_min=scale_min,
            scale_max=scale_max,
            value_field=value_field,  # type: ignore
            bar_height_multiplier=bar_height_multiplier,
            polygon_height_multiplier=polygon_height_multiplier,
            polygon_fill_opacity=polygon_fill_opacity,
            polygon_outline=polygon_outline,
            show_labels=show_labels,
            interpolation_mode=interpolation_mode  # type: ignore
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid export options: {exc}"
        ) from exc

    # Generate CZML
    service = CZMLExportService()
    try:
        czml_json = service.export(selection, options, index_type=index_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc)
        ) from exc
    czml_document = json.loads(czml_json)

    # Normalise empty strings to None for optional ownership fields
    czml_id = czml_id.strip() if czml_id else None
    user_id = user_id.strip() if user_id else None
    project_id = project_id.strip() if project_id else None

    # Save to database if requested
    db_czml_id = ""
    replaced = False
    
    if save_to_db:
        czml_record = CZMLRecord(
            czml_id=czml_id,
            selection_ref=id,
            index_type=index_type,
            title=f"{selection.title}_{index_type}_{visualisation_type}",
            description=f"CZML export of {selection.title} ({index_type}) as {visualisation_type}",
            user_id=user_id,
            project_id=project_id,
            export_options=options,
            czml_document=czml_document,
            packet_count=len(czml_document)
        )
        
        czml_repo = CZMLRepository()
        db_czml_id, replaced = czml_repo.save_czml(czml_record)
        
        logger.info(
            "CZML exported: id=%s, selection=%s, index=%s, type=%s, packets=%d, replaced=%s",
            db_czml_id, id, index_type, visualisation_type, len(czml_document), replaced
        )

    return CZMLExportResponse(
        czml_id=db_czml_id,
        selection_ref=id,
        index_type=index_type,
        visualisation_type=visualisation_type,
        packet_count=len(czml_document),
        replaced=replaced,
        czml_document=czml_document
    )


@router.get(
    "/czml/{id}",
    summary="Get saved CZML document",
    description="Retrieve a previously exported CZML document by ID."
)
async def get_czml_document(
    id: str = Path(..., description="MongoDB ObjectId of the CZML document")
) -> dict:
    """Fetch a saved CZML document by its ID."""
    czml_repo = CZMLRepository()
    record = czml_repo.get_czml(id)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CZML document not found: {id}"
        )
    
    return record.model_dump(by_alias=True)


@router.get(
    "/czml/by-czml-id/{czmlID}",
    summary="Get saved CZML document by czmlID (UUID)",
    description="Retrieve a previously exported CZML document by frontend-generated UUID."
)
async def get_czml_by_czml_id(
    czmlID: str = Path(..., description="Frontend-generated UUID (czmlID)")
) -> dict:
    """Fetch a saved CZML document by its frontend-generated czmlID (UUID)."""
    czml_repo = CZMLRepository()
    record = czml_repo.get_czml_by_czml_id(czmlID)
    
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CZML document not found with czmlID: {czmlID}"
        )
    
    return record.model_dump(by_alias=True)


@router.get(
    "/selections/{id}/czml",
    summary="List CZML documents for selection",
    description="Get all CZML documents generated for a selection."
)
async def list_czml_for_selection(
    id: str = Path(..., description="MongoDB ObjectId of the selection"),
    index_type: Optional[str] = Query(
        None,
        alias="indexType",
        description="Filter by climate index type: ppet, wbgt, etc."
    ),
    visualisation_type: Optional[str] = Query(
        None,
        alias="visualisationType",
        description="Filter by visualisation type: bar, polygon"
    )
) -> List[dict]:
    """List all CZML documents for a selection."""
    czml_repo = CZMLRepository()
    records = czml_repo.get_czml_by_selection(id, index_type, visualisation_type)
    
    return [record.model_dump(by_alias=True) for record in records]


@router.delete(
    "/czml/{id}",
    summary="Delete CZML document",
    description="Delete a saved CZML document."
)
async def delete_czml_document(
    id: str = Path(..., description="MongoDB ObjectId of the CZML document")
) -> dict:
    """Delete a saved CZML document."""
    czml_repo = CZMLRepository()
    deleted = czml_repo.delete_czml(id)
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CZML document not found: {id}"
        )
    
    return {"deleted": True, "id": id}


@router.put(
    "/czml/{id}",
    summary="Update CZML document metadata",
    description="Update metadata fields for an existing CZML document. Only provided fields are updated. "
                "This does not regenerate the CZML — use /export-czml for that."
)
async def update_czml_document(
    id: str = Path(..., description="MongoDB ObjectId of the CZML document"),
    title: Optional[str] = Form(None, description="CZML document title"),
    description: Optional[str] = Form(None, description="CZML document description"),
    user_id: Optional[str] = Form(None, alias="userID", description="Owner user UUID"),
    project_id: Optional[str] = Form(None, alias="projectID", description="Project UUID"),
) -> dict:
    """Update CZML document metadata fields."""
    # Check at least one field is provided
    if all(v is None for v in [title, description, user_id, project_id]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (title, description, userID, projectID) must be provided."
        )

    czml_repo = CZMLRepository()
    updated = czml_repo.update_czml_metadata(
        id,
        title=title,
        description=description,
        user_id=user_id,
        project_id=project_id,
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CZML document not found: {id}"
        )

    return {
        "message": "CZML document updated successfully",
        "czml": updated.model_dump(by_alias=True),
    }
