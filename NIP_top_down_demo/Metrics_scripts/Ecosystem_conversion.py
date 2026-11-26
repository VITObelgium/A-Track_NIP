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

"""DEMONSTRATION ONLY: tailored to one site/case, experimental input maps. See ../../LIMITATIONS_AND_CAVEATS.md before use.

Ecosystem conversion (step 1.4, Conversion of one ecosystem type to another): where did the priority ecosystems go
between the opening and closing habitat maps.

The net difference in the extent table does not show real conversion: an increase in a class can come from other
classes turning into it. Here the two maps are compared pixel by pixel, which is a simple method (it is biased when the
maps are made independently; a change detection workflow is preferred). For every priority class (level 2 and/or 3,
set in EA_setup.py) the destination class at levels 1, 2 and 3 is given with area (ha), pixel count and percentage of
the priority class's opening area - e.g. the share of the priority grassland that became constructed/artificial (J).

Uses the clipped rasters of Ecosystem_extent.py (extent_output_dir), so the analysis area, buffer and nodata are
identical to the extent tables. Output (in conversion_output_dir):
priority_ecosystems_transitions_detailed_buffer{N}m.csv
"""
# %% Imports - run this block first when running block by block
import numpy as np
import pandas as pd
import rasterio

from EA_setup import (
    buffer_size_m, extent_output_dir, conversion_output_dir, pixel_resolution_m, priority_level2, priority_level3,
    lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column, lut_level_column,
)
from EA_utils import get_pixel_resolution, load_lut, eunis_code_at_level

# %%
# ==========================================================================
# STEP 1: Load the clipped rasters and the LUT
# ==========================================================================
# Reads the clipped opening and closing maps made by Ecosystem_extent.py (run that script first), checks they are on
# the same grid and reads the LUT. Creates: habitat_opening, habitat_closing, value_to_code, pixel_area_ha.

opening_path = extent_output_dir / f"clipped_opening_buffer{buffer_size_m}m.tif"
closing_path = extent_output_dir / f"clipped_closing_buffer{buffer_size_m}m.tif"
for path in (opening_path, closing_path):
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run Ecosystem_extent.py (with an opening and closing raster) first")

with rasterio.open(opening_path) as src_open, rasterio.open(closing_path) as src_close:
    if src_open.shape != src_close.shape or src_open.transform != src_close.transform:
        raise ValueError("Opening and closing rasters are not on the same grid (shape/transform differ), "
                         "pixel-by-pixel comparison is not possible")
    habitat_opening = src_open.read(1)
    habitat_closing = src_close.read(1)
    nodata_opening = src_open.nodata
    nodata_closing = src_close.nodata

pixel_resolution = pixel_resolution_m if pixel_resolution_m is not None else get_pixel_resolution(opening_path)
pixel_area_ha = pixel_resolution ** 2 / 10000
print(f"Pixel resolution: {pixel_resolution}m")

lut3, _ = load_lut(lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column, lut_level_column)
value_to_code = dict(zip(lut3['raster_value'], lut3['eunis_code']))

# %%
# ==========================================================================
# STEP 2: Count pixel transitions and map them to EUNIS codes at levels 1, 2 and 3
# ==========================================================================
# Counts the pixels per (from, to) raster value pair on pixels that are valid in both years and maps each pair to EUNIS
# codes at levels 1, 2 and 3. Creates: pairs. Prints the valid area and a warning for values missing from the LUT.

valid = np.ones(habitat_opening.shape, dtype=bool)
if nodata_opening is not None:
    valid &= habitat_opening != nodata_opening
if nodata_closing is not None:
    valid &= habitat_closing != nodata_closing

# Count per unique (from, to) raster value pair first, so the code mapping is done once per pair
pairs = pd.DataFrame({'from_value': habitat_opening[valid], 'to_value': habitat_closing[valid]})
pairs = pairs.groupby(['from_value', 'to_value']).size().reset_index(name='n_pixels')
total_pixels = pairs['n_pixels'].sum()
print(f"Valid pixels in both years: {total_pixels} ({total_pixels * pixel_area_ha:.2f} ha)")

unmapped = sorted(set(pairs['from_value']).union(pairs['to_value']) - set(value_to_code))
if unmapped:
    print(f"Warning: raster values not in the LUT (reported as 'Unknown'): {unmapped}")

for side in ('from', 'to'):
    code3 = pairs[f'{side}_value'].map(value_to_code).fillna('Unknown')
    for level in (1, 2, 3):
        pairs[f'{side}_lvl{level}'] = code3.map(lambda c: eunis_code_at_level(c, level))

# %%
# ==========================================================================
# STEP 3: Priority ecosystems - where did they go (destinations at all three levels)
# ==========================================================================
# For each priority class (priority_level2 / priority_level3 in EA_setup.py) lists the destination classes with area (ha),
# pixels and % of the class, and saves the csv in conversion_output_dir.

priority_rows = []
for level, classes in ((2, priority_level2), (3, priority_level3)):
    from_col = f'from_lvl{level}'
    to_col = f'to_lvl{level}'
    for priority_class in classes:
        sub = pairs[pairs[from_col] == priority_class]
        if sub.empty:
            print(f"Note: priority class {priority_class} (level {level}) not present in the opening map")
            continue
        class_pixels = sub['n_pixels'].sum()
        dest = sub.groupby(['to_lvl1', 'to_lvl2', 'to_lvl3'], as_index=False)['n_pixels'].sum()
        # 'changed' compares the destination with the priority class at the priority class's own level
        dest['changed'] = dest[to_col] != priority_class
        dest.insert(0, 'from_class', priority_class)
        dest.insert(1, 'from_level', level)
        dest['area_ha'] = dest['n_pixels'] * pixel_area_ha
        dest['percent_of_class'] = dest['n_pixels'] / class_pixels * 100
        priority_rows.append(dest)

priority_df = pd.concat(priority_rows, ignore_index=True)[
    ['from_class', 'from_level', 'to_lvl1', 'to_lvl2', 'to_lvl3', 'area_ha', 'n_pixels', 'percent_of_class', 'changed']
] if priority_rows else pd.DataFrame()
conversion_output_dir.mkdir(parents=True, exist_ok=True)
detailed_path = conversion_output_dir / f"priority_ecosystems_transitions_detailed_buffer{buffer_size_m}m.csv"
priority_df.to_csv(detailed_path, index=False)
print(f"Saved: {detailed_path}")
