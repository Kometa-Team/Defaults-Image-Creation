# Numerical Reference Data

The 34 numerical reference pairs in `ciede2000-reference.txt` are from Gaurav
Sharma, Wencheng Wu and Edul N. Dalal, *The CIEDE2000 Color-Difference Formula:
Implementation Notes, Supplementary Test Data, and Mathematical Observations*,
Color Research & Application 30(1), 2005, DOI 10.1002/col.20070.

[Author's reference data](https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/dataNprograms/ciede2000testdata.txt)
and [paper](https://hajim.rochester.edu/ece/sites/gsharma/papers/CIEDE2000CRNAFeb05.pdf).

Only numerical validation facts are transcribed, with whitespace normalized.
No MATLAB, Excel, third-party software or library implementation was downloaded,
installed or copied. `color_math.py` independently expresses the paper's equations
with unit weighting factors and is checked against every pair in both directions
to the published four-decimal precision. This is not an official CIE implementation
or a claim of psychophysical validation. Advisory thresholds remain configuration.
