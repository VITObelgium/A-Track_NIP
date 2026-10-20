# A-Track

Tools and demonstration material from the A-Track project for structuring nature data along a Nature Information
Pathway (NIP).

> **Please read [Case1_top_down_demo/IMPORTANT_READ_FIRST.md](Case1_top_down_demo/IMPORTANT_READ_FIRST.md) before using
> anything here.** The scripts are for demonstration only, and the input maps are experimental.

## Contents

| Folder | What it is |
|---|---|
| [`Case1_top_down_demo/`](Case1_top_down_demo/README.md) | Python scripts and demo input data to repeat *Case 1: Tracking impacts on stocks at priority locations* (A-Track D2.2b, top-down demonstration): ecosystem extent, transformations, conversion, connectivity and grassland productivity. |

## Quick start

```
git clone https://github.com/EvansAlexandra/A-Track.git
cd A-Track/Case1_top_down_demo
pip install -r requirements.txt
python Ecosystem_extent.py
```

Then follow the run order in the [demo README](Case1_top_down_demo/README.md). Outputs are written to
`Case1_top_down_demo/outputs/`. Tip: install the geospatial packages (geopandas, rasterio) with conda if pip fails on
your system.

## Licence and data

The code is under the licence in [LICENSE](LICENSE). The data keep their own licences and sources: see
[Case1_top_down_demo/DATA_REFERENCES.md](Case1_top_down_demo/DATA_REFERENCES.md).