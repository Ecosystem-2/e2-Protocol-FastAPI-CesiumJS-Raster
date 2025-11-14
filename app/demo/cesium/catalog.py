from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import rasterio

REPO_ROOT = Path(__file__).resolve().parents[3]

HUMID_PALETTE = (
    "#00e676",  # 1: Low
    "#ffee58",  # 2: Elevated
    "#ffb347",  # 3: Moderate
    "#ff7043",  # 4: High
    "#2d142c",  # 5: Extreme
)

PPET_PALETTE = (
    "#f1f8ff",
    "#c7e9ff",
    "#9ad0ff",
    "#6bb8ff",
    "#3fa1f4",
    "#1c87d3",
    "#0d6ab1",
    "#084d8a",
    "#063a69",
    "#04254a",
)


@dataclass(frozen=True)
class DemoLayer:
    collection_id: str
    collection_label: str
    id: str
    label: str
    path: Path
    start_date: date
    end_date: date
    colormap: str = "Spectral"
    fade_years: int = 6
    bounds: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    gradient: tuple[str, str] = ("#f5deb3", "#f04f5a")
    palette: tuple[str, ...] | None = None

    @property
    def fade_seconds(self) -> int:
        return int(self.fade_years * 365.25 * 24 * 3600)

    def to_dict(self) -> dict[str, object]:
        return {
            "collection_id": self.collection_id,
            "collection_label": self.collection_label,
            "id": self.id,
            "label": self.label,
            "start": self.start_date.isoformat(),
            "end": self.end_date.isoformat(),
            "colormap": self.colormap,
            "fade_seconds": self.fade_seconds,
            "bounds": {
                "west": self.bounds[0],
                "south": self.bounds[1],
                "east": self.bounds[2],
                "north": self.bounds[3],
            },
            "gradient": {"start": self.gradient[0], "end": self.gradient[1]},
            "palette": list(self.palette) if self.palette else None,
        }


def _read_bounds(path: Path) -> tuple[float, float, float, float]:
    with rasterio.open(path) as src:
        b = src.bounds
    return (b.left, b.bottom, b.right, b.top)


def _layer(
    *,
    collection_id: str,
    collection_label: str,
    layer_id: str,
    label: str,
    relative_path: str,
    start: date,
    end: date,
    colormap: str,
    fade_years: int = 6,
    gradient: tuple[str, str] = ("#f5deb3", "#f04f5a"),
    palette: tuple[str, ...] | None = None,
) -> DemoLayer:
    path = REPO_ROOT / relative_path
    bounds = _read_bounds(path)
    return DemoLayer(
        collection_id=collection_id,
        collection_label=collection_label,
        id=layer_id,
        label=label,
        path=path,
        start_date=start,
        end_date=end,
        colormap=colormap,
        fade_years=fade_years,
        bounds=bounds,
        gradient=gradient,
        palette=palette,
    )


def _build_catalog() -> dict[str, tuple[DemoLayer, ...]]:
    humid = (
        _layer(
            collection_id="humid-heat-stress",
            collection_label="Humid Heat Stress (WBGT)",
            layer_id="historic",
            label="Historic (1981–2010)",
            relative_path="data/humid-heat-stress/geotif/Segama_Historic_1981-2010_WBGT-Sun_Max_threat_level.tif",
            start=date(1981, 1, 1),
            end=date(2010, 12, 31),
            colormap="inferno",
            gradient=("#00e676", "#ffee58"),
            palette=HUMID_PALETTE,
        ),
        _layer(
            collection_id="humid-heat-stress",
            collection_label="Humid Heat Stress (WBGT)",
            layer_id="mid-century",
            label="Mid-century (2041–2070)",
            relative_path="data/humid-heat-stress/geotif/Segama_All245_2041-2070_WBGT-Sun_Max_threat_level.tif",
            start=date(2041, 1, 1),
            end=date(2070, 12, 31),
            colormap="inferno",
            gradient=("#ffb347", "#ff7043"),
            palette=HUMID_PALETTE,
        ),
        _layer(
            collection_id="humid-heat-stress",
            collection_label="Humid Heat Stress (WBGT)",
            layer_id="late-century",
            label="Late-century (2071–2100)",
            relative_path="data/humid-heat-stress/geotif/Segama_All245_2071-2100_WBGT-Sun_Max_threat_level.tif",
            start=date(2071, 1, 1),
            end=date(2100, 12, 31),
            colormap="inferno",
            gradient=("#2d142c", "#2d142c"),
            palette=HUMID_PALETTE,
        ),
    )

    ppet = (
        _layer(
            collection_id="p-pet-ratio",
            collection_label="P/PET Ratio",
            layer_id="historic",
            label="Historic (1981–2010)",
            relative_path="data/p-pet-ratio/geotif/Segama_historic_1981-2010_PPET_ConDryMth.tif",
            start=date(1981, 1, 1),
            end=date(2010, 12, 31),
            colormap="viridis",
            gradient=("#a7ffeb", "#12cbc4"),
            palette=PPET_PALETTE,
        ),
        _layer(
            collection_id="p-pet-ratio",
            collection_label="P/PET Ratio",
            layer_id="mid-century",
            label="Mid-century (2041–2070)",
            relative_path="data/p-pet-ratio/geotif/Segama_All245_2041-2070_PPET_ConDryMth.tif",
            start=date(2041, 1, 1),
            end=date(2070, 12, 31),
            colormap="viridis",
            gradient=("#12cbc4", "#1289a7"),
            palette=PPET_PALETTE,
        ),
        _layer(
            collection_id="p-pet-ratio",
            collection_label="P/PET Ratio",
            layer_id="late-century",
            label="Late-century (2071–2100)",
            relative_path="data/p-pet-ratio/geotif/Segama_All245_2071-2100_PPET_ConDryMth.tif",
            start=date(2071, 1, 1),
            end=date(2100, 12, 31),
            colormap="viridis",
            gradient=("#1289a7", "#0652dd"),
            palette=PPET_PALETTE,
        ),
    )

    return {
        "humid-heat-stress": humid,
        "p-pet-ratio": ppet,
    }


CATALOG: dict[str, tuple[DemoLayer, ...]] = _build_catalog()
LAYER_LOOKUP: dict[tuple[str, str], DemoLayer] = {
    (layer.collection_id, layer.id): layer
    for layers in CATALOG.values()
    for layer in layers
}


def iter_layers() -> Iterable[DemoLayer]:
    for layers in CATALOG.values():
        for layer in layers:
            yield layer


def get_layer(collection_id: str, layer_id: str) -> DemoLayer:
    key = (collection_id, layer_id)
    if key not in LAYER_LOOKUP:
        raise KeyError(f"Unknown layer '{layer_id}' for collection '{collection_id}'.")
    return LAYER_LOOKUP[key]


LEGEND_INFO = {
    "humid-heat-stress": {
        "palette": list(HUMID_PALETTE),
        "labels": ["Low Threat", "Elevated Threat", "Moderate Threat", "High Threat", "Extreme Threat"],
    },
    "p-pet-ratio": {
        "palette": list(PPET_PALETTE),
        "labels": [f"Class {i}" for i in range(1, len(PPET_PALETTE) + 1)],
    },
}


def catalogue_payload() -> dict[str, object]:
    start = min(layer.start_date for layer in iter_layers())
    end = max(layer.end_date for layer in iter_layers())
    extent = _global_extent()
    collections: list[dict[str, object]] = []
    for collection_id, layers in CATALOG.items():
        legend = LEGEND_INFO.get(
            collection_id,
            {"palette": [], "labels": []},
        )
        collections.append(
            {
                "id": collection_id,
                "label": layers[0].collection_label if layers else collection_id,
                "extent": _extent_for_layers(layers),
                "layers": [layer.to_dict() for layer in layers],
                "legend_palette": list(legend["palette"]),
                "legend_labels": list(legend["labels"]),
            }
        )

    return {
        "timeline": {"start": start.isoformat(), "end": end.isoformat()},
        "collections": collections,
        "extent": extent,
    }


def _extent_for_layers(layers: Iterable[DemoLayer]) -> dict[str, float]:
    layer_list = list(layers)
    west = min(layer.bounds[0] for layer in layer_list)
    south = min(layer.bounds[1] for layer in layer_list)
    east = max(layer.bounds[2] for layer in layer_list)
    north = max(layer.bounds[3] for layer in layer_list)
    return {"west": west, "south": south, "east": east, "north": north}


def _global_extent() -> dict[str, float]:
    return _extent_for_layers(list(iter_layers()))
