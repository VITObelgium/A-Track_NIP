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

Grassland productivity (step 1.4, Ecosystem-specific condition metrics): total primary productivity (TPP/TPROD,
Copernicus VPP) of the priority grassland classes (R1, R2, R3) in the site, the site plus a buffer, and a reference
site (e.g. a well-managed protected grassland in the landscape), to show how the site's grassland condition compares
and changes between years.

Run Download_TPROD.py first to get the raw TPROD tiles. The tiles (10 m) are resampled onto each habitat map grid (nodata 65535 excluded, 0 kept as a valid value,
overlapping tiles averaged, scale factor applied) and the TPROD values on the grassland pixels are summarised per
class. Only the tiles that touch an area are read.

In the document the landscape is the 50 km buffer; for size constraints only the 500 m buffer raster is provided, so
the site is compared with the site + 500 m (set productivity_buffer_m and larger maps to widen it).

Areas: the site polygon, the site polygon + productivity_buffer_m and (if its habitat maps are given) the reference
site. All settings are in EA_setup.py. Output (in productivity_output_dir):
  - grassland_productivity_statistics.csv
  - tprod_{area}_{year}.tif (TPROD on the grassland pixels, -9999 = no data)
  - tprod_comparison.png (mean pixel TPROD per class, per year, per area)
"""
# %% Imports - run this block first when running block by block
import re

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask

from EA_setup import (
    site_polygon_path, raster_opening_path, raster_closing_path, year_labels,
    lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column, lut_level_column,
    tprod_dir, tprod_scale, productivity_codes, productivity_code_level, productivity_buffer_m,
    ref_site_label, ref_polygon_path, ref_raster_opening_path, ref_raster_closing_path, site_raster_level,
    ref_raster_level, productivity_output_dir,
)
from EA_utils import (
    load_lut, habitat_raster_values, buffer_geodataframe, validate_geometry_within_raster, check_landscape_coverage,
    clip_raster_to_geometry, find_tprod_tiles, tprod_on_grid, tprod_statistics, plot_tprod_comparison,
)

COLOURS = ['#002060', '#C00000', '#ED7D31']
NO_DATA_OUT = -9999.0

# %%
# ==========================================================================
# STEP 1: LUT, habitat codes and areas
# ==========================================================================
# Reads the LUT (raster values per class, for each map level), the site polygon and the reference site polygon, and
# defines the areas to compare. Creates: code_values, areas. Stops if a map does not cover its area (the reference
# maps may miss some of the contour; that is reported in step 2).

if raster_closing_path is None or (ref_raster_opening_path is None) != (ref_raster_closing_path is None):
    raise ValueError("Opening and closing habitat maps are needed for the site (and for the reference site, if used)")
productivity_output_dir.mkdir(parents=True, exist_ok=True)

# Raster values per class, for each map level in use (the reference maps can be at another level than the site maps)
lookups, code_values = {}, {}
for level in {site_raster_level, ref_raster_level}:
    if level < productivity_code_level:
        raise ValueError(f"A level {level} map cannot be used for level {productivity_code_level} classes")
    lookups[level], names = load_lut(lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column,
                                     lut_level_column, map_level=level)
    code_values[level] = {code: habitat_raster_values(lookups[level], [code], productivity_code_level)
                          for code in productivity_codes}
    print(f"Raster values per class for level {level} maps: {code_values[level]}")

gdf_site = gpd.read_file(site_polygon_path)
if gdf_site.crs is None:
    raise ValueError("Site polygon has no CRS defined")

# area label -> (geometry, (opening map, closing map), map level, extent check)
areas = {"Site": (gdf_site, (raster_opening_path, raster_closing_path), site_raster_level, 'within')}
if productivity_buffer_m > 0:
    areas[f"Site + {productivity_buffer_m} m"] = (
        buffer_geodataframe(gdf_site, productivity_buffer_m), (raster_opening_path, raster_closing_path),
        site_raster_level, 'landscape')
if ref_raster_opening_path is not None:
    gdf_ref = gpd.read_file(ref_polygon_path)
    if gdf_ref.crs is None:
        raise ValueError("Reference site polygon has no CRS defined")
    # The reference maps may not cover the polygon contour completely; the data coverage is reported below
    areas[ref_site_label] = (gdf_ref, (ref_raster_opening_path, ref_raster_closing_path), ref_raster_level, 'partial')
else:
    print("No reference site habitat maps given (ref_raster_opening_path / ref_raster_closing_path): skipping it")

for label, (gdf, paths, level, check) in areas.items():
    for path in paths:
        if check == 'within':
            validate_geometry_within_raster(gdf, path, label)
        elif check == 'landscape':
            check_landscape_coverage(gdf, path, productivity_buffer_m)

# %%
# ==========================================================================
# STEP 2: TPROD per area, year and class
# ==========================================================================
# For each area and year: clips the habitat map, resamples the TPROD tiles onto its grid, and calculates the TPROD
# statistics per class. Creates: rows. Prints the tiles used, the data coverage of the polygon and the stats per class,
# and saves a tif of the TPROD on the grassland pixels.

rows = []
for label, (gdf, paths, level, _) in areas.items():
    slug = re.sub(r'[^A-Za-z0-9]+', '_', label).strip('_')
    for year, habitat_path in zip(year_labels, paths):
        habitat, profile = clip_raster_to_geometry(habitat_path, gdf)
        crs, transform = profile['crs'], profile['transform']
        if crs.is_geographic:
            raise ValueError(f"{habitat_path.name} has a geographic CRS; a projected CRS is needed for areas")
        pixel_area_ha = abs(transform.a * transform.e) / 10_000
        valid = ~np.ma.getmaskarray(habitat)
        polygon_pixels = int((~geometry_mask(gdf.to_crs(crs).geometry, out_shape=habitat.shape,
                                             transform=transform)).sum())
        coverage_pct = 100 * valid.sum() / polygon_pixels

        tiles = find_tprod_tiles(tprod_dir, year, gdf)
        tprod = tprod_on_grid(tiles, transform, habitat.shape, crs, tprod_scale)
        print(f"\n{label} - {year}: tiles {[t.name.split('_')[3] for t in tiles]}; habitat map has data for "
              f"{coverage_pct:.1f}% of the polygon")

        habitat_values = np.ma.getdata(habitat)
        unmapped = sorted(set(np.unique(habitat_values[valid]).tolist()) - set(lookups[level]['raster_value']))
        if unmapped:
            print(f"  Note: raster values not in the level {level} LUT (not assigned to any class): {unmapped}")
        all_grassland = np.zeros(habitat.shape, dtype=bool)
        for code in productivity_codes:
            mask = np.isin(habitat_values, code_values[level][code]) & valid
            all_grassland |= mask
            stats = tprod_statistics(tprod, mask, pixel_area_ha)
            rows.append(dict(area=label, year=int(year), habitat_code=code,
                             habitat_name=names[productivity_code_level].get(code, ''),
                             polygon_data_coverage_pct=coverage_pct, **stats))
            print(f"  {code}: {stats['area_ha']:.2f} ha, mean TPROD {stats['mean_tprod']:.2f} "
                  f"({stats['n_pixels_with_tprod']}/{stats['n_pixels']} pixels with TPROD)")

        out = np.where(all_grassland & np.isfinite(tprod), tprod, NO_DATA_OUT).astype('float32')
        profile.update(dtype='float32', nodata=NO_DATA_OUT, count=1)
        tif_path = productivity_output_dir / f"tprod_{slug}_{year}.tif"
        with rasterio.open(tif_path, 'w', **profile) as dst:
            dst.write(out, 1)

# %%
# ==========================================================================
# STEP 3: Statistics table and comparison plot
# ==========================================================================
# Saves the statistics table (csv) and the comparison plot (mean pixel TPROD per class, year and area).

stats_df = pd.DataFrame(rows)
stats_path = productivity_output_dir / "grassland_productivity_statistics.csv"
stats_df.to_csv(stats_path, index=False, float_format="%.3f")

plot_path = productivity_output_dir / "tprod_comparison.png"
plot_tprod_comparison(stats_df, list(areas), productivity_codes, [int(y) for y in year_labels], COLOURS, plot_path)

print(f"\n{stats_df[['area', 'year', 'habitat_code', 'area_ha', 'mean_tprod', 'median_tprod']].to_string(index=False)}")
print(f"\nSaved: {stats_path}\nSaved: {plot_path}")