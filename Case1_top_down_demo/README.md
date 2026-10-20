# A-Track D2.2b: ecosystem extent and condition scripts

> **WARNING - DEMONSTRATION ONLY.** These scripts are tailored to one site and case and use experimental, unvalidated input maps. **[Please read IMPORTANT_READ_FIRST.md before using them](IMPORTANT_READ_FIRST.md).** Data sources and licences: **[DATA_REFERENCES.md](DATA_REFERENCES.md)** (note: the demo LUT is site-specific and must not be reused elsewhere).

Python scripts for the Nature Information Pathway "Tracking impacts on stocks at priority locations": steps **1.3
(treatments to organise data - ecosystem extent)** and **1.4 (application-focused transformation of data)** of the
A-Track D2.2b document. They turn EUNIS habitat maps for an opening and a closing year (2021 and 2024 in the demo) into
extent tables, summary plots, conversion tables, connectivity metrics and productivity (condition) statistics.

## Structure

| File | Role |
|---|---|
| `IMPORTANT_READ_FIRST.md` | Demonstration-only warning and data caveats. Read first. |
| `DATA_REFERENCES.md` | Sources and licences of all input data; why the demo LUT cannot be reused. |
| `EA_setup.py` | **All user settings**: paths, LUT columns, buffer, years, priority classes, connectivity and productivity settings, output folders. Edit this, not the scripts. |
| `EA_utils.py` | All helper functions used by the scripts (raster clipping, LUT reading, aggregation, maps, plots, patches and graphs, TPROD). |
| `Ecosystem_extent.py` | Step 1.3 |
| `Extent_transformations.py` | Step 1.4 |
| `Ecosystem_conversion.py` | Step 1.4 |
| `Ecosystem_connectivity.py` | Step 1.4 |
| `Download_TPROD.py` | Step 1.4 (download of the TPROD input tiles) |
| `Grassland_productivity.py` | Step 1.4 |

## How to use

- **Only edit `EA_setup.py`.** Set your paths and options there (base folder, input files, LUT column names, buffer, years, priority classes, etc.). **Do not edit `EA_utils.py`** - it contains the functions the scripts rely on. The scripts themselves should not need changes.
- **Run a script in full** (e.g. `python Ecosystem_extent.py`, or run it from your IDE), **or block by block** to see the printed output at each step. Every script is divided in blocks marked with `# %%`, each with a short comment saying what it does, what it prints and which variables it creates (in PyCharm or VS Code, run one block at a time with the cell/"Run Cell" command or by selecting it).
- When running block by block, **run the first block (imports) and then the blocks in order**: later blocks use the variables created by earlier ones. Settings are always read from `EA_setup.py`, so after changing it, restart (re-run the imports block).

## Input data (`demo_input_data`, set in `EA_setup.py`)

- `Site_polygon.gpkg`: site boundary.
- `y2021_lvl3_500m.tif`, `y2024_lvl3_500m.tif`: habitat maps (EUNIS level 3, single band, nodata -1, 10 m).
- `site_lut.csv`: lookup table (`;`-separated) with raster values, EUNIS codes, names and levels.
- `EUNIS_threatStatus.csv`: Red List threat status per EUNIS class.
- `TPROD\`: raw Copernicus VPP TPROD tiles (about 200 MB each, so **not supplied**: `Download_TPROD.py` downloads them). The demo needs T30UWD and T30UWE (2021 and 2024).
- `UKNSN\`: reference site polygon (`Peake_district_dales32630.gpkg`) and its habitat maps (`RefHabitat_y*_EUNISlvl2.tif`, EUNIS level 2).
- `EUNIS2021plus_legend_lvl3_subset.qml`: legend that colours the jpg maps.

## Run order

1. **`Ecosystem_extent.py`** - run first. Its output is the input of the transformations and conversion scripts.
2. **`Extent_transformations.py`**
3. **`Ecosystem_conversion.py`**
4. **`Ecosystem_connectivity.py`**
5. **`Download_TPROD.py`** (once, needs a free WEkEO account - see the script header), then **`Grassland_productivity.py`**

Steps 2-5 follow the order of the document (ecosystem overviews, conversion, connectivity, then ecosystem-specific
condition). After step 1 they are independent of each other, except that 2 and 3 need the outputs of 1.

## What each script does

- **Ecosystem_extent** - clips the habitat maps to the site (+ optional buffer) and calculates the area of each EUNIS class at levels 1, 2 and 3 (with names), and exports the clipped maps (tif, jpg).
- **Extent_transformations** - plots the level 1 areas with natural habitats aggregated vs anthropogenic classes, and the area per Red List threat status.
- **Ecosystem_conversion** - pixel-by-pixel comparison of the two maps: where did the priority classes go (e.g. grassland to constructed/artificial).
- **Ecosystem_connectivity** - habitat patch connectivity of the site and its landscape: patches, IIC, mean nearest neighbour distance, effective mesh size, stepping-stone importance (dIIC) and reachable habitat, for several dispersal distances.
- **Download_TPROD** - downloads the Copernicus HR-VPP TPROD tiles that cover the site (+ buffer) and the reference site for each year, from WEkEO, into the TPROD folder (credentials in ~/.hdarc or HDA_USER/HDA_PASSWORD; pip install hda).
- **Grassland_productivity** - total primary productivity of the priority grassland pixels in the site, the site + buffer and a reference site, per year.

## Outputs

Every script writes to its own subfolder of the `outputs` folder:

```
outputs\
  Ecosystem_extent\        habitat_areas_lvl1/2/3 csv, clipped maps (tif, jpg)
  Extent_transformations\  level 1 and threat status plots and table
  Ecosystem_conversion\    priority_ecosystems_transitions_detailed csv
  Ecosystem_connectivity\  summary csv, report, patch / graph GeoPackages, maps
  Grassland_productivity\  statistics csv, TPROD tifs, comparison plot
```

## Notes

- Level 1 classes without child classes (C, J, M) appear at several LUT levels; they are counted once and stay as they are at all levels.
- The ecosystem extent, transformation and conversion scripts need level 3 habitat maps. The connectivity and productivity scripts also accept coarser maps (`site_raster_level`, `ref_raster_level`).
- The document uses a 50 km landscape (productivity) and a 10 km landscape (connectivity). For size constraints, only the 500 m buffer rasters are provided, so the demo landscape is the site + 500 m (`LANDSCAPE_RADIUS_M` in the connectivity script, `productivity_buffer_m` in the productivity script). With larger habitat maps, increase these settings to reproduce the document's landscapes.
- The net difference between two independently made maps is not true ecosystem change; the conversion script uses a simple pixel-by-pixel comparison, and a change detection workflow is preferred for real applications.
- Requirements: Python with numpy, pandas, geopandas, shapely, rasterio, matplotlib, scipy, scikit-image and networkx.
