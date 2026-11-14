---
hide:
  - toc
---

# Validation map

Every count station of the six counties against the simulated 2024 traffic: observed weekday volumes with and
without trucks, the matched network links with their simulated volumes and direction, by road class. Click a station
to see its numbers and to highlight the links it is matched to; use the layer control to show I-695 only or to hide
local roads.

[:material-fullscreen: Open the map full screen](../../assets/maps/validation_map.html){ .md-button .md-button--primary target="_blank" }

<iframe src="../../../assets/maps/validation_map.html" title="Traffic assignment against the 2024 counts"
        style="width:100%; height:78vh; border:1px solid var(--md-default-fg-color--lightest); border-radius:6px;"
        loading="lazy"></iframe>

The map carries the residents' traffic only; trucks, commercial vehicles and through traffic are not simulated, so
simulated volumes are expected to fall below the counts. Results: [Traffic](traffic.md).
