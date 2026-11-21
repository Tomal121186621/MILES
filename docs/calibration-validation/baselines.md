# Comparison with standard methods

Each stage is to be run against an established alternative, with the same inputs, targets, hold-out data and measures,
and with no variant fitted to traffic counts:

- **Population synthesis**: the conditional variational autoencoder against iterative proportional fitting with a
  weighted draw, iterative proportional updating (PopulationSim) and weighted sampling of the training households.
- **Land use**: against the original SILO Maryland model, calibrated with the same procedure.
- **Activities**: MAST against the original activity set-up and a standard tour-based model.
- **Assignment**: the same network and assignment with the original activity demand.

The comparison is updated after the final runs. The validation of each stage against observed data is on the
[validation pages](validation/index.md).
