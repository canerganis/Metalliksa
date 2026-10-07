# Attribution and license

`tracks.csv` is a table extracted from `Allegati/Data.xlsx` inside `Allegati.zip` of the Mendeley Data record
https://data.mendeley.com/datasets/s9438vb5xd/1 (DOI 10.17632/s9438vb5xd.1, v1, 2021-04-26), licensed
**CC BY 4.0** (https://creativecommons.org/licenses/by/4.0/). The SEM images of the record are NOT included.

Changes made: the workbook sheets 'Track width (W)', 'Track depth (D)', 'Track height (H)' and
'Contact angle' (8 powers x 10 speeds each) were merged into one long table
`power_W,speed_mm_s,width_um,depth_um,height_um,contact_angle_deg` (80 rows; floats rounded to 15 significant
digits as text). The microhardness sheet is not included. Units as stated in the workbook (um, deg).

Source workbook: 20,097 bytes, SHA-256 3211cbaa9fe29f1126ea25666cb6de902335aa4cd974dc0918d1c247a31c1e42.
The workbook itself does not state the reference line of the track depth; the associated paper does (see below).

Depth datum and spot definition (settled from the associated paper, Vaglio et al. 2020, Data in Brief, Fig. 1,
Fig. 2(b), Sec. 1.3 and Sec. 2): `depth_um` is measured from the top surface of the printed Ti-6Al-4V base (below the
25 um powder layer) down to the track bottom, and `height_um` is above that surface; the powder layer thickness is
drawn separately in Fig. 1. The spot is 50 um "according to the 1/e^2 classical definition" (M^2 = 1.08, 1070 nm). The
base was printed in the same job (Table 3), so it is not a wrought plate; preheat is not stated. The data file is
unchanged by this note (its SHA-256 pin is unaffected).

Please cite: Totis, Vaglio et al., single-track Ti6Al4V SEM images and geometrical data (Concept Laser M2,
50 um laser spot), Mendeley Data, doi:10.17632/s9438vb5xd.1; related article Data in Brief,
doi:10.1016/j.dib.2020.106443.

Measured values of a third party; used here only to COMPARE screening kernels, not as experimental validation.
