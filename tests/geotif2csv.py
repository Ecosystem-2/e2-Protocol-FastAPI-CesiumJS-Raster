# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import logging
from pathlib import Path
import tqdm
import pandas as pd

from app.geotif_converter.raster2dataframe import raster_to_dataframe
from app.geotif_converter.raster_io import read_geotiff
from app.core.logging import get_logger

logger = get_logger(__name__)

project_root = Path(__file__).parent.parent
# data_folder = project_root / "data" / "humid-heat-stress" 
data_folder = project_root / "data" / "p-pet-ratio" 
geotif_folder = data_folder / "geotif"
geotif_files = list(geotif_folder.glob("*.tif"))

# csv_filename = data_folder/"ssp245_WBGT_Sun_Segama_River_combined.csv"
csv_filename = data_folder/"p-pet-ratio_Segama_River_combined.csv"

df0 = pd.DataFrame()
for file in tqdm.tqdm(geotif_files):
    raster = read_geotiff(file)
    variable_name = file.name.replace(".tif", "").lower()

    df = raster_to_dataframe(raster, variable_name=variable_name, exclude_columns=["band", "spatial_ref"], xy_decimal=6)
    if df0.columns.empty:
        df0 = df
    else:
        df0 = df0.merge(df, on=["x", "y"], how="outer")

df0.reset_index(drop=True, inplace=True)
df0.dropna(subset=df0.columns[3:], how="all", inplace=True)
df0.reset_index(drop=True, inplace=True)

# df0.fillna(0, inplace=True)
df0.to_csv(csv_filename, index=True)
    




