"""DEMONSTRATION ONLY: tailored to one site/case, experimental input maps. See IMPORTANT_READ_FIRST.md before use.

Download the Copernicus HR-VPP Total Productivity (TPROD) tiles needed by Grassland_productivity.py (run this first).

The raw tiles are large (about 200 MB each), so they are not supplied with the repository. This script finds the 10 m
Sentinel-2 tiles that intersect the site (plus buffer) and the reference site, for each year in EA_setup.year_labels,
and downloads them to EA_setup.tprod_dir through the WEkEO Harmonised Data Access (HDA) service. Tiles already in the
folder are skipped, so it is safe to re-run. Only season 1 tiles (..._s1_TPROD.tif) are kept, as in the demo.

Before running (one-off):
  1. Create a free WEkEO account (https://www.wekeo.eu) and accept the Copernicus terms when asked.
  2. pip install hda
  3. Provide your credentials, either in a file called .hdarc in your home folder (two lines: "user: <name>" and
     "password: <password>") or as the environment variables HDA_USER and HDA_PASSWORD. Never put them in the scripts.

Data: Copernicus Land Monitoring Service, HR-VPP Total Productivity
(https://land.copernicus.eu/en/products/vegetation/high-resolution-total-productivity). Acknowledge the source when
using it (see DATA_REFERENCES.md).
"""
import geopandas as gpd

from EA_setup import site_polygon_path, year_labels, tprod_dir, productivity_buffer_m, ref_polygon_path, \
    ref_raster_opening_path
from EA_utils import buffer_geodataframe, gdf_bounds_wgs84, download_tprod_tiles

# %%
# ==========================================================================
# STEP 1: areas to cover
# ==========================================================================
# Reads the site polygon (plus the productivity buffer) and, if reference site maps are given, the reference polygon.
# Prints the bounding box (lon/lat) that is searched. Creates: gdfs.

gdf_site = gpd.read_file(site_polygon_path)
if gdf_site.crs is None:
    raise ValueError("Site polygon has no CRS defined")
gdfs = [buffer_geodataframe(gdf_site, productivity_buffer_m) if productivity_buffer_m > 0 else gdf_site]
if ref_raster_opening_path is not None:
    gdf_ref = gpd.read_file(ref_polygon_path)
    if gdf_ref.crs is None:
        raise ValueError("Reference site polygon has no CRS defined")
    gdfs.append(gdf_ref)
print("Search bounding box [lon_min, lat_min, lon_max, lat_max]:", [round(v, 4) for v in gdf_bounds_wgs84(gdfs)])
print("Years:", year_labels, "-> saving to", tprod_dir)

# %%
# ==========================================================================
# STEP 2: search and download
# ==========================================================================
# Searches WEkEO for the TPROD tiles intersecting the bounding box, lists the tiles found per year, and downloads the
# ones that are not yet in tprod_dir (this can take a while: about 200 MB per tile). Creates: tiles.

tiles = download_tprod_tiles(gdfs, year_labels, tprod_dir)
print("\nTiles available in", tprod_dir)
for tile in tiles:
    print(" ", tile.name)
print("\nNote: the bounding box can select neighbouring tiles that are not needed; Grassland_productivity.py only uses "
      "the tiles that intersect the areas.")