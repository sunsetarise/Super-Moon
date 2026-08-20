# SM35 CAD qualification report

The implemented matrix requires CadQuery/OCCT to STEP to OCCT, direct OCCT to
IGES to OCCT, assembly to STEP, and source-to-tessellation comparison. Each row
requires BRep validity, translator completion, topology preservation, evidence,
and prespecified volume, area, and centroid drift limits.

CadQuery and OCP/OCCT are unavailable locally. Both STEP and direct-OCCT IGES
physical qualification gates therefore remain open. The driver deliberately
does not label IGES as CadQuery-native support.
