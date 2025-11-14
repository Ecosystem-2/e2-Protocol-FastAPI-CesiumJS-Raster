from __future__ import annotations

from pathlib import Path
from typing import Union, Mapping, Literal, Any, BinaryIO
import logging

from rasterio.io import MemoryFile
import rioxarray
import xarray as xr
from rasterio.crs import CRS

PathLike = Union[str, Path]
BytesLike = Union[bytes, bytearray, memoryview]


logger = logging.getLogger(__name__)


def read_geotiff(
    source: PathLike | BytesLike | BinaryIO,
    *,
    masked: bool = True,
    load: bool = False,
    chunks: Mapping[str, int] | int | Literal["auto"] | None = None,
    target_crs: str = "EPSG:4326",
) -> xr.DataArray:
    """Load a GeoTIFF raster into an xarray.DataArray.

    Parameters
    ----------
    source:
        Filesystem path or GeoTIFF bytes / binary file-like object.
    masked:
        Whether to mask nodata values. Defaults to True to preserve nodata as NaNs.
    load:
        If True, eagerly load the array into memory; otherwise keep it lazy.
        In-memory byte sources are always loaded eagerly.
    chunks:
        Dask chunking to enable out-of-core processing for large rasters. Use a
        mapping like {"x": 1024, "y": 1024} or an integer for uniform chunking,
        or "auto" to let xarray choose. Defaults to None (no chunking).
    target_crs:
        The CRS to convert the raster to. Defaults to EPSG:4326.
    """

    def _ensure_crs_and_reproject(da: xr.DataArray, *, source_label: str) -> xr.DataArray:
        if target_crs:
            if da.rio.crs is None:
                raise ValueError(f"Source CRS is missing and cannot reproject: {source_label}")
            if CRS.from_user_input(target_crs) != da.rio.crs:
                da = da.rio.reproject(target_crs)
        return da

    def _finalise(da: xr.DataArray, *, source_label: str, force_load: bool = False) -> xr.DataArray:
        da = _ensure_crs_and_reproject(da, source_label=source_label)
        if load or force_load:
            da = da.load()
        return da

    if isinstance(source, (str, Path)):
        raster_path = Path(source)
        if not raster_path.is_file():
            raise FileNotFoundError(f"GeoTIFF not found: {raster_path}")

        data = rioxarray.open_rasterio(raster_path, masked=masked, chunks=chunks)
        return _finalise(data, source_label=str(raster_path), force_load=False)

    data_bytes = _coerce_bytes(source)
    if not data_bytes:
        raise ValueError("GeoTIFF payload is empty.")

    with MemoryFile(data_bytes) as memfile:
        with memfile.open() as dataset:
            data = rioxarray.open_rasterio(dataset, masked=masked, chunks=chunks)
            return _finalise(data, source_label="uploaded GeoTIFF", force_load=True)



def get_raster_metadata(raster: xr.DataArray) -> dict[str, Any]:
    """Summarise key metadata and basic stats for a raster.

    Returns a dictionary including dimensions, CRS, transform, resolution,
    bounds, variable naming/units and basic value statistics.
    """

    # Basic geometry and CRS
    transform = raster.rio.transform()
    bounds_vals = raster.rio.bounds()
    try:
        res_x, res_y = raster.rio.resolution()
    except Exception:  # fallback from transform (y may be negative)
        res_x, res_y = transform.a, abs(transform.e)

    crs = raster.rio.crs
    epsg = crs.to_epsg() if crs is not None else None

    # Dimensions and sizes
    dims = tuple(raster.dims)
    sizes = {k: int(v) for k, v in raster.sizes.items()}
    band_count = sizes.get("band", 1)

    # Variable naming and units
    variable_name = raster.name
    units = raster.attrs.get("units")
    long_name = raster.attrs.get("long_name")
    scale_factor = raster.attrs.get("scale_factor")
    add_offset = raster.attrs.get("add_offset")

    # Nodata and simple stats (NaN-safe; may trigger compute with dask)
    nodata = raster.rio.nodata
    rmin = raster.min(skipna=True)
    rmax = raster.max(skipna=True)
    rmean = raster.mean(skipna=True)
    rstd = raster.std(skipna=True)

    # Render scalar values (support dask/xarray scalars)
    def _scalar(val: Any) -> Any:
        try:
            if hasattr(val, "compute"):
                val = val.compute()
            if hasattr(val, "item"):
                return val.item()
            return val
        except Exception:
            return None

    # Support both tuple and namedtuple returns from bounds()
    try:
        left = bounds_vals.left  # type: ignore[attr-defined]
        bottom = bounds_vals.bottom  # type: ignore[attr-defined]
        right = bounds_vals.right  # type: ignore[attr-defined]
        top = bounds_vals.top  # type: ignore[attr-defined]
    except Exception:
        left, bottom, right, top = tuple(bounds_vals)

    info: dict[str, Any] = {
        # "dims": dims,
        "sizes": sizes,
        "dtype": str(raster.dtype),
        "crs": crs,
        "epsg": epsg,
        "transform": transform,
        "resolution": (abs(res_x), abs(res_y)),
        "bounds": {"left": left, "bottom": bottom, "right": right, "top": top},
        # "band_count": band_count,
        "variable_name": variable_name,
        "long_name": long_name,
        "units": units,
        "scale_factor": scale_factor,
        "add_offset": add_offset,
        "nodata": nodata,
        "min": _scalar(rmin),
        "max": _scalar(rmax),
        "mean": _scalar(rmean),
        "std": _scalar(rstd),
    }

    # Optional time extent summary
    if "time" in raster.dims:
        try:
            tmin = _scalar(raster["time"].min())
            tmax = _scalar(raster["time"].max())
            info["time_extent"] = {"start": tmin, "end": tmax}
        except Exception:
            info["time_extent"] = None

    return info



def _coerce_bytes(source: BytesLike | BinaryIO) -> bytes:
    if isinstance(source, (bytes, bytearray, memoryview)):
        return bytes(source)

    read = getattr(source, "read", None)
    if callable(read):
        data = read()
        if isinstance(data, str):
            raise TypeError("GeoTIFF stream returned text; expected bytes.")
        return data or b""

    raise TypeError("Unsupported GeoTIFF source; expected path, bytes, or binary file-like object.")
