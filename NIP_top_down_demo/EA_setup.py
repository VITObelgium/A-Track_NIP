# Author: Alexandra Evans <alexandra.evans@vito.be>
# Copyright © 2026 VITO
#
# SPDX-FileCopyrightText: 2026 VITO
# SPDX-License-Identifier: MIT
#
# Please acknowledge the author and copyright holder in outputs produced using these scripts.
#
# Licensed under the MIT License.
# See LICENCE-SCRIPTS.md in the repository root for the licence terms.

"""User settings for all metrics and download scripts - check the paths and options below, then run the modules in
Metrics_scripts as described in the repository's README.md."""
from pathlib import Path

# ==========================================================================
# SETUP - Define paths and settings here
# ==========================================================================

# Working folder: the folder of this script (inputs are read from Demo_input_data, outputs go to outputs). No need to
# change it; to use data or outputs elsewhere, change the paths below.
base_dir = Path(__file__).resolve().parent
# Choose a site buffer size in meters for analysis: between 0 (no buffer, default) and 500
buffer_size_m = 0

############################################################################
### Input data - the following is configured for running the A-Track D2.2b demo with the provided data
inputs = base_dir / "Demo_input_data"
# Site polygon (shp or gpkg)
site_polygon_path = inputs / "Demo_site" / "Demo_site_polygon.gpkg"

# Habitat map rasters (tif, single band, EUNIS level 3 here, for 2021 & 2024)
raster_opening_path = inputs / "Demo_site" / "DemoHabitat_y2021_EUNISlvl3_buffered.tif"
raster_closing_path = inputs / "Demo_site" / "DemoHabitat_y2024_EUNISlvl3_buffered.tif"  # None: opening year only

# EUNIS level of the site habitat maps. Ecosystem_extent, Extent_transformations and Ecosystem_conversion need level 3
# maps; Ecosystem_connectivity and Grassland_productivity also work with coarser maps (down to the habitat level).
site_raster_level = 3

# Pixel resolution in meters - set to None to auto-detect from each raster, or specify manually (used for all rasters)
pixel_resolution_m = None  # e.g., 10 for 10m resolution

# Lookup table (csv) with one row per class on levels 1, 2 and 3. The level 3 rows link the map's raster values to
# codes; rows of all levels provide the names for the level 1, 2 and 3 output tables.
lut_path = inputs / "Demo_lookup_tables" / "LUT_EUNIS_GET_demo.csv"
lut_separator = ";"
lut_value_column = "rasterValue"
lut_code_column = "EUNIS2021plus_Code"
lut_name_column = "EUNIS2021plus_Name"
lut_level_column = "EUNIS2021plus_Level"

# QGIS style file (.qml, paletted raster) with the class colours, used for the jpg maps (set to None to skip the jpgs)
legend_qml_path = inputs / "EUNIS2021plus_legend_lvl3_subset.qml"

### Outputs - every script writes to its own subfolder of the outputs folder
output_dir = base_dir / "outputs"
extent_output_dir = output_dir / "Ecosystem_extent"
transformations_output_dir = output_dir / "Extent_transformations"
conversion_output_dir = output_dir / "Ecosystem_conversion"
connectivity_output_dir = output_dir / "Ecosystem_connectivity"
productivity_output_dir = output_dir / "Grassland_productivity"

############################################################################
### Settings shared by the analysis scripts
# Labels for the opening and closing year
year_labels = ("2021", "2024")

############################################################################
### Extent_transformations.py
# EUNIS threat status table (csv) and its settings
threat_csv = inputs / "Demo_lookup_tables" / "LUT_EUNIS_RedList_demo.csv"
threat_separator = ";"
threat_encoding = "latin-1"
threat_code_column = "Code"
threat_status_column = "Threat"
# Order of the threat categories on the x axis
threat_order = ["CR", "EN", "VU", "NT", "LC", "DD"]

# Plot 1: natural classes (shown individually and summed in the 'Natural habitats' stacked bar) and the other
# classes, each as {label: EUNIS level 1 code}, in plotting order
natural_groups = {
    "Coastal": "N",
    "Heathland scrub": "S",
    "Wetlands": "Q",
    "Forest": "T",
    "Grasslands": "R",
}
other_groups = {
    "Vegetated man-made": "V",
    "Constructed industrial": "J",
    "Inland surface waters": "C",
    "Sparse/bare": "U",
}
class_colours = {
    "Coastal": "#4db6ac", "Heathland scrub": "#c58f3c", "Wetlands": "#5c8dd6", "Forest": "#2e7d32",
    "Grasslands": "#9ccc65",
    "Vegetated man-made": "#ffd21f", "Constructed industrial": "#7f7f7f", "Inland surface waters": "#29b6f6",
    "Sparse/bare": "#bcaaa4",
}

############################################################################
### Ecosystem_conversion.py
priority_level2 = ['R1', 'R2', 'R3']  # level 2 priority classes
priority_level3 = ['R1A', 'R1M', 'R1P', 'R21', 'R22', 'R35', 'R36', 'R37']  # level 3 priority classes

############################################################################
### Ecosystem_connectivity.py (site = the site polygon; landscape = the site polygon plus the radius below)
# Habitat to analyse: EUNIS codes at a given level (level 2: ['R1', 'R2', 'R3'] = all grassland; level 1: ['R'])
habitat_label = "Grassland"
habitat_codes = ['R1', 'R2', 'R3']
habitat_code_level = 2

# Minimum mapping unit (ha) for habitat patches
MIN_AREA_HA = 0.1

# Dispersal distances (m) for the sensitivity analysis. E.g. 100 m = sedentary specialists, 200 m = most grassland
# invertebrates and plants, 500 m = mobile species. The headline distance must be one of them.
DISPERSAL_THRESHOLDS = [100, 200, 500]
HEADLINE_THRESHOLD = 200

# Landscape around the site polygon (m) in which patches are included for the landscape analysis. The habitat
# maps need to cover the site plus this radius.
LANDSCAPE_RADIUS_M = 500

############################################################################
### Grassland_productivity.py
# Folder with the raw Copernicus VPP TPROD tiles (VPP_{year}_S2_*_TPROD.tif); only the tiles that cover the areas are
# used (for the demo: T30UWD and T30UWE, for both years). Download_TPROD.py fills this folder for your areas.
tprod_dir = inputs / "TPROD"
# Scale factor applied to the TPROD values (Copernicus VPP). The tile nodata (65535) is excluded; 0 is a valid value.
tprod_scale = 0.1

# Habitat to analyse: EUNIS codes at a given level (level 2: ['R1', 'R2', 'R3'] = the grassland classes)
productivity_codes = ['R1', 'R2', 'R3']
productivity_code_level = 2

# The site polygon is compared with the site plus this buffer (m) - the habitat maps must cover it
productivity_buffer_m = 500

# Reference site: polygon and habitat maps (opening, closing; same LUT as the site). Set the maps to None to skip it.
ref_site_label = "Peak District Dales"
ref_polygon_path = inputs / "Reference_site" / "Peake_district_dales32630.gpkg"
ref_raster_opening_path = inputs / "Reference_site" / "RefHabitat_y2021_EUNISlvl2.tif"
ref_raster_closing_path = inputs / "Reference_site" / "RefHabitat_y2024_EUNISlvl2.tif"
# EUNIS level of the reference site habitat maps (must be at least productivity_code_level)
ref_raster_level = 2
