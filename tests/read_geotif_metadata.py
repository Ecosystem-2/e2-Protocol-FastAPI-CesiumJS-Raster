# SPDX-FileCopyrightText: 2025-2026 Ecosystem2 Ltd
# SPDX-FileCopyrightText: 2025-2026 Yang Zhang
# SPDX-License-Identifier: AGPL-3.0-or-later

from __future__ import annotations

import logging
from pathlib import Path
import sys
import tqdm
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from app.geotif_converter.raster_io import read_geotiff, get_raster_metadata
from app.geotif_converter.raster_vis import plot_raster, plot_raster_discrete
from app.commons.file_io import write_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# data_folder = PROJECT_ROOT / "data" / "humid-heat-stress" 
data_folder = PROJECT_ROOT / "data" / "p-pet-ratio" 
geotif_folder = data_folder / "geotif"
geotif_files = list(geotif_folder.glob("*.tif"))
metadata_folder = data_folder / "metadata"

metadata_folder.mkdir(parents=True, exist_ok=True)

for file in tqdm.tqdm(geotif_files):
    filename = file.name
    data = read_geotiff(file)

    title = filename.replace('.tif', '').replace('_', ' ').title()
    plot_save_path = data_folder / "vis" / f"{filename.replace('.tif', '.png')}"
    # plot_raster(data, title=title, save_path=plot_save_path)
    plot_raster_discrete(
        data, 
        title=title, 
        save_path=plot_save_path, 
        levels=(1, 2, 3, 4, 5, 6), 
        labels=("Low Threat", "Elevated Threat", "Moderate Threat", "High Threat", "Extreme Threat", "Critical Threat"), 
        colours=("limegreen", "yellow", "orange", "red", "black", "magenta"),
        alpha=0.9,
        transparent=False,
    )

    info = get_raster_metadata(data)
    write_json(metadata_folder / f"{filename.replace('.tif', '.json')}", info, atomic=True)
