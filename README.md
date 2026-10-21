# A-Track

Tools and demonstration material from the A-Track project for structuring nature data along a Nature Information
Pathway (NIP).

> **Please read [IMPORTANT_READ_FIRST.md](NPI_top_down_demo/IMPORTANT_READ_FIRST.md) before using
> anything here.** The scripts are for demonstration only, and the input maps are experimental.

## Contents

| Folder | What it is |
|---|---|
| [`NPI_top_down_demo`](NPI_top_down_demo/README.md) | Python scripts and demo input data to repeat *Case 1: Tracking impacts on stocks at priority locations* (A-Track D2.2b, top-down demonstration): ecosystem extent, transformations, conversion, connectivity and grassland productivity. |

## Start here

1. Read the [important information](NPI_top_down_demo/IMPORTANT_READ_FIRST.md) and
   [data sources and licences](NPI_top_down_demo/DATA_REFERENCES.md), including the restrictions on reusing the demo lookup table.
2. Follow the [repository and Python setup guide](NPI_top_down_demo/README.md#repository-and-python-setup),
   with instructions for [PyCharm and VS Code](NPI_top_down_demo/README.md#pycharm-or-vs-code).
3. Open [`EA_setup.py`](NPI_top_down_demo/EA_setup.py), check the paths for your computer and optionally adjust the
   analysis settings. The bundled demo paths are relative to this file, so moving the whole repository does not require
   changing them.
4. Run the [setup check](NPI_top_down_demo/README.md#check-your-setup) to check dependencies and configured paths.
5. Run the scripts in [`Metrics_scripts`](NPI_top_down_demo/Metrics_scripts) in the
   [document's demo order](NPI_top_down_demo/README.md#run-the-demo-in-document-order).

The [demo README](NPI_top_down_demo/README.md) explains the folder layout, settings, inputs and expected outputs.
Generated results go to `NPI_top_down_demo\outputs`, not into the scripts or input-data folders.
The extent, transformations, conversion and connectivity examples use the bundled data; productivity additionally
requires downloading Copernicus TPROD tiles with a free WEkEO account.

## Licence and data

The code is under the licence in [LICENSE](LICENSE). The data keep their own licences and sources: see
[DATA_REFERENCES.md](NPI_top_down_demo/DATA_REFERENCES.md).