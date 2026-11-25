"""DEMONSTRATION ONLY: tailored to one site/case, experimental input maps. See LIMITATIONS_AND_CAVEATS.md before use.

Ecosystem extent (step 1.3, Ecosystem extent): the area (ha) of each EUNIS class in the site, for the opening and
closing year.

The habitat maps are clipped to the site polygon (plus an optional buffer of up to 500 m) and the area of each class
is the number of pixels times the pixel area. This gives a SEEA-aligned ecosystem extent account: tables at EUNIS
levels 1, 2 and 3 (aggregated separately, so nothing is double counted; names included) plus the clipped maps (tif,
jpg, coloured with the class legend). Note that the net difference between two independently made maps is not true
ecosystem change. Run this script first: the other scripts build on its output.

All settings are in EA_setup.py. Output (in extent_output_dir): habitat_areas_lvl{1,2,3}_buffer{N}m.csv and
clipped_{opening,closing}_buffer{N}m.tif / .jpg
"""
# %% Imports - run this block first when running block by block
import geopandas as gpd
import rasterio

from EA_setup import (
    buffer_size_m, extent_output_dir, site_polygon_path, raster_opening_path, raster_closing_path, pixel_resolution_m,
    lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column, lut_level_column, legend_qml_path,
    site_raster_level,
)
from EA_utils import (
    get_pixel_resolution, buffer_geodataframe, validate_geometry_within_raster, clip_raster_to_geometry,
    calculate_pixel_stats, load_lut, add_eunis_codes, aggregate_to_level, read_qml_palette, export_map_image,
)

extent_output_dir.mkdir(parents=True, exist_ok=True)

# %%
# ==========================================================================
# STEP 1: Load site polygon and apply buffer
# ==========================================================================
# Reads the site polygon and applies the buffer (buffer_size_m). Creates: gdf_site, gdf_analysis (the area that is clipped).
# Prints the number of features and the buffer applied.

if not 0 <= buffer_size_m <= 500:
    raise ValueError(f"buffer_size_m must be between 0 and 500, got {buffer_size_m}")
if site_raster_level != 3:
    raise ValueError("Ecosystem_extent needs level 3 habitat maps (site_raster_level = 3)")

gdf_site = gpd.read_file(site_polygon_path)
if gdf_site.crs is None:
    raise ValueError("Site polygon has no CRS defined")
print(f"Site polygon loaded: {len(gdf_site)} feature(s)")

gdf_analysis = buffer_geodataframe(gdf_site, buffer_size_m)
print(f"Buffer of {buffer_size_m}m applied to site polygon" if buffer_size_m > 0 else "No buffer applied - using original site polygon")

# %%
# ==========================================================================
# STEP 2: Validate geometry against raster extents and get pixel resolution
# ==========================================================================
# Checks that the analysis area lies within each raster and gets the pixel size. Creates: raster_paths, pixel_resolutions.
# Stops with an error if the area is not covered by a raster.

raster_paths = {'opening': raster_opening_path}
if raster_closing_path:
    raster_paths['closing'] = raster_closing_path

analysis_name = f"Analysis area (buffer={buffer_size_m}m)"
for year, path in raster_paths.items():
    validate_geometry_within_raster(gdf_analysis, path, analysis_name)
    print(f"Analysis area is within {year} raster extent")

pixel_resolutions = {}
for year, path in raster_paths.items():
    if pixel_resolution_m is None:
        pixel_resolutions[year] = get_pixel_resolution(path)
        print(f"Pixel resolution of {year} raster auto-detected: {pixel_resolutions[year]}m")
    else:
        pixel_resolutions[year] = pixel_resolution_m
        print(f"Using specified pixel resolution for {year} raster: {pixel_resolution_m}m")

# %%
# ==========================================================================
# STEP 3: Load LUT
# ==========================================================================
# Reads the LUT. Creates: lut (raster value -> EUNIS code at level 3) and names (EUNIS names per level).

lut, names = load_lut(lut_path, lut_separator, lut_value_column, lut_code_column, lut_name_column, lut_level_column)

# %%
# ==========================================================================
# STEP 4: Clip rasters and calculate habitat areas per EUNIS code
# ==========================================================================
# Clips each raster to the analysis area and sums the area (ha) per EUNIS code. Creates: clipped, profiles (the clipped
# maps) and stats (area per code). Prints the clipped shapes and a warning for raster values missing from the LUT.

clipped = {}
profiles = {}
stats = {}
for year, path in raster_paths.items():
    clipped[year], profiles[year] = clip_raster_to_geometry(path, gdf_analysis)
    print(f"\n{year.capitalize()} year raster clipped: shape = {clipped[year].shape}")
    stats[year] = add_eunis_codes(calculate_pixel_stats(clipped[year], pixel_resolutions[year]), lut, year)
    stats[year] = stats[year].rename(columns={'area_ha': f'area_ha_{year}'})

# %%
# ==========================================================================
# STEP 5: Create level 3, 2 and 1 tables (separate, so nothing is double counted)
# ==========================================================================
# Builds the level 3, 2 and 1 area tables (each aggregated separately, so nothing is double counted), prints them and
# saves them as csv in extent_output_dir.

area_columns = [f'area_ha_{year}' for year in raster_paths]

combined = stats['opening']
if 'closing' in stats:
    combined = combined.merge(stats['closing'], on='eunis_code', how='outer').fillna(0)
combined = combined.rename(columns={'eunis_code': 'EUNIS_code'})

for level in (3, 2, 1):
    table = aggregate_to_level(combined, level, names, area_columns)
    print(f"\nEUNIS level {level} habitat areas (ha):")
    print(table.to_string(index=False))
    out_path = extent_output_dir / f"habitat_areas_lvl{level}_buffer{buffer_size_m}m.csv"
    table.to_csv(out_path, index=False)
    print(f"Saved: {out_path}")

# %%
# ==========================================================================
# STEP 6: Export clipped rasters (tif) and maps (jpg)
# ==========================================================================
# Saves the clipped maps as tif and, if a legend (.qml) is set in EA_setup.py, as jpg maps with title, legend and scale bar.

palette = read_qml_palette(legend_qml_path) if legend_qml_path else None

for year in raster_paths:
    out_path = extent_output_dir / f"clipped_{year}_buffer{buffer_size_m}m.tif"
    with rasterio.open(out_path, "w", **profiles[year]) as dest:
        dest.write(clipped[year].filled(profiles[year]['nodata']), 1)
    print(f"Saved: {out_path}")

    if legend_qml_path:
        jpg_path = extent_output_dir / f"clipped_{year}_buffer{buffer_size_m}m.jpg"
        export_map_image(clipped[year], palette, jpg_path, f"Ecosystem extent - {year} year (buffer {buffer_size_m}m)",
                         pixel_resolutions[year], names=names[3])
        print(f"Saved: {jpg_path}")
