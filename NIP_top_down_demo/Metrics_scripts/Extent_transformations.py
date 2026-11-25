"""DEMONSTRATION ONLY: tailored to one site/case, experimental input maps. See LIMITATIONS_AND_CAVEATS.md before use.

Extent transformations (step 1.4, Transformation of extent data for ecosystem overviews): summary plots of the
extent tables.

1. Area of each EUNIS level 1 class for the opening and closing year, with the natural classes (coastal, heathland/
   scrub, wetlands, forest, grassland) summed as 'Natural habitats' and compared with the anthropogenic and other
   classes: vegetated man-made (V), constructed (J), inland surface waters (C) and sparse/bare (U).
2. Area per IUCN Red List of Habitats threat status (from the EUNIS threat status table), for both years.

Reads the tables of Ecosystem_extent.py (extent_output_dir); output goes to transformations_output_dir.
"""
# %% Imports - run this block first when running block by block
import pandas as pd

from EA_setup import (
    buffer_size_m, extent_output_dir, transformations_output_dir, year_labels, threat_csv, threat_separator, threat_encoding, threat_code_column,
    threat_status_column, threat_order, natural_groups, other_groups, class_colours,
)
from EA_utils import load_threat_lookup, aggregate_by_threat_status, plot_level1_summary, plot_threat_status

transformations_output_dir.mkdir(parents=True, exist_ok=True)

# %%
# ==========================================================================
# Load tables made by Ecosystem_extent.py
# ==========================================================================
# Reads the level 1 and level 3 tables made by Ecosystem_extent.py (run that script first).
# Creates: lvl1, lvl3, area_columns.

area_columns = ["area_ha_opening", "area_ha_closing"]
lvl1 = pd.read_csv(extent_output_dir / f"habitat_areas_lvl1_buffer{buffer_size_m}m.csv")
lvl3 = pd.read_csv(extent_output_dir / f"habitat_areas_lvl3_buffer{buffer_size_m}m.csv")

# %%
# ==========================================================================
# PLOT 1: level 1 class areas, natural habitats vs other
# ==========================================================================
# Plots the area per level 1 class: natural classes individually and summed as 'Natural habitats' vs the other classes.
# Saves a png (settings: natural_groups, other_groups, class_colours in EA_setup.py).

plot_path = transformations_output_dir / f"area_by_level1_class_buffer{buffer_size_m}m.png"
plot_level1_summary(lvl1, natural_groups, other_groups, class_colours, area_columns, year_labels, plot_path)
print(f"Saved: {plot_path}")

# %%
# ==========================================================================
# PLOT 2: area per threat status
# ==========================================================================
# Sums the level 3 areas per Red List threat status and plots them. Prints the area per status and the habitats
# without a status (these are excluded). Saves a csv and a png.

threat_lookup = load_threat_lookup(threat_csv, threat_separator, threat_encoding,
                                   threat_code_column, threat_status_column)
agg, no_status = aggregate_by_threat_status(lvl3, threat_lookup, area_columns, threat_order)

print("\nArea (ha) per threat status:")
print(agg.round(2).to_string(index=False))
print("\nHabitats without a threat status (excluded; not assessed or not in the threat table):")
print(no_status.round(2).to_string(index=False))
print(f"Total area without status: {no_status[area_columns].sum().round(2).tolist()} ha "
      f"of {lvl3[area_columns].sum().round(2).tolist()} ha")

csv_path = transformations_output_dir / f"area_by_threat_status_buffer{buffer_size_m}m.csv"
agg.round(2).to_csv(csv_path, index=False)
print(f"Saved: {csv_path}")

plot_path = transformations_output_dir / f"area_by_threat_status_buffer{buffer_size_m}m.png"
plot_threat_status(agg, area_columns, year_labels, plot_path)
print(f"Saved: {plot_path}")