from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, Mapping, Union

import pandas as pd
import xarray as xr
from app.geotif_converter.raster_io import read_geotiff
from app.core.logging import get_logger


__all__ = ["raster_to_dataframe"]

logger = get_logger(__name__)



def raster_to_dataframe(
    raster: xr.DataArray,
    *,
    variable_name: str = "value",
    drop_na: bool = False,
    exclude_columns: list[str] = [],
    xy_decimal: int = 6,
) -> pd.DataFrame:
    """Convert a raster into a tidy pandas DataFrame.
    Args:
        raster: Raster to convert to a DataFrame.
        variable_name: Column name to use for raster values.
        drop_na: Drop rows where the value is NaN (nodata typically maps to NaN).
        exclude_columns: Columns to exclude from the DataFrame.
        xy_decimal: Number of decimal places to round the x and y coordinates to.

    Examples:
        >>> raster = read_geotiff("data/Humid Heat Stress/geotif/ssp245_WBGT_Sun_2041_2070_Segama_River.tif")
        >>> df = raster_to_dataframe(raster, variable_name="value", drop_na=False, exclude_columns=["band", "spatial_ref"], xy_decimal=7)
        >>> print(df)

    Returns:
        A pandas DataFrame in long format with dimension columns and a value column.
    """

    df = raster.to_dataframe(name=variable_name).reset_index()

    if drop_na:
        df = df.dropna(subset=[variable_name])

    if exclude_columns:
        df = df.drop(columns=exclude_columns, errors="ignore")

    if xy_decimal:
        df["x"] = df["x"].round(xy_decimal)
        df["y"] = df["y"].round(xy_decimal)

    return df




# --- Test code ---

if __name__ == "__main__":
    raster = read_geotiff("data/Humid Heat Stress/geotif/ssp245_WBGT_Sun_2041_2070_Segama_River.tif")
    df = raster_to_dataframe(
        raster,
        variable_name="ssp245_WBGT_Sun_2041_2070",
        drop_na=False,
        exclude_columns=["band", "spatial_ref"],
        xy_decimal=7,
    )
    print(df)