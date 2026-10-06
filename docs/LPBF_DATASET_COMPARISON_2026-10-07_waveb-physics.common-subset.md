# LPBF dataset comparison: common subset ddd8358a -> f3ba9896

Schema `lpbf-dataset-common-subset-1`. Rule: per kernel, rows with extentStatus == 'computed' in BOTH records; ratio = model / measured. Comparison against published single-track measurements; not validation; nothing fitted. `experimentalValidation` = false.

| kernel | group | n | W MAPE % | D MAPE % | W bias % | D bias % |
| --- | --- | ---: | --- | --- | --- | --- |
| rosenthal | all-datasets | 743 | 32.3 -> 30.5 | 50.1 -> 56.3 | 12.5 -> 19.5 | 37.4 -> 47.1 |
| rosenthal | hofmann-316l-2026 | 604 | 28.1 -> 25.8 | 52.0 -> 59.4 | 5.9 -> 13.7 | 44.5 -> 55.6 |
| rosenthal | ku-leuven-316l-2021 | 44 | 56.2 -> 57.7 | 43.4 -> 44.0 | 56.2 -> 57.7 | -9.5 -> -8.4 |
| rosenthal | ku-leuven-ti64-2021 | 14 | 33.7 -> 37.0 | 65.2 -> 69.0 | 33.7 -> 37.0 | 62.8 -> 66.8 |
| rosenthal | lane-in625-2020 | 6 | 23.2 -> 10.4 | 38.5 -> 29.4 | -23.2 -> -10.4 | -38.5 -> -29.4 |
| rosenthal | pooled-summary-scope | 679 | 30.8 -> 28.8 | 50.3 -> 57.1 | 9.5 -> 16.9 | 40.6 -> 51.0 |
| rosenthal | totis-ti64-2021 | 75 | 52.7 -> 53.1 | 36.6 -> 38.5 | 38.9 -> 43.1 | 9.9 -> 13.9 |
| eagar-tsai | all-datasets | 838 | 13.9 -> 12.0 | 33.9 -> 36.0 | -9.0 -> -2.7 | 9.8 -> 15.1 |
| eagar-tsai | hofmann-316l-2026 | 677 | 13.5 -> 10.7 | 34.3 -> 36.9 | -10.5 -> -4.2 | 14.5 -> 20.4 |
| eagar-tsai | ku-leuven-316l-2021 | 44 | 12.5 -> 16.7 | 29.0 -> 29.0 | 3.7 -> 12.2 | -12.9 -> -12.9 |
| eagar-tsai | ku-leuven-ti64-2021 | 14 | 13.7 -> 8.4 | 28.6 -> 28.6 | -13.7 -> -7.8 | 21.2 -> 21.2 |
| eagar-tsai | lane-in625-2020 | 23 | 15.5 -> 20.1 | 27.5 -> 25.2 | 7.8 -> 15.3 | -26.4 -> -14.2 |
| eagar-tsai | pooled-summary-scope | 757 | 13.9 -> 11.6 | 34.4 -> 36.8 | -10.2 -> -4.0 | 12.0 -> 17.5 |
| eagar-tsai | totis-ti64-2021 | 80 | 18.1 -> 18.7 | 35.4 -> 36.5 | -8.1 -> -2.2 | -9.3 -> -7.1 |
| goldak | all-datasets | 817 | 19.8 -> 15.7 | 37.5 -> 40.7 | -16.7 -> -9.5 | 16.4 -> 21.5 |
| goldak | hofmann-316l-2026 | 665 | 20.1 -> 15.2 | 38.3 -> 42.0 | -18.2 -> -11.0 | 21.7 -> 27.4 |
| goldak | ku-leuven-316l-2021 | 44 | 12.6 -> 16.1 | 29.0 -> 29.0 | 2.4 -> 11.0 | -12.9 -> -12.9 |
| goldak | ku-leuven-ti64-2021 | 14 | 16.6 -> 11.0 | 28.6 -> 28.6 | -16.6 -> -10.6 | 21.2 -> 21.2 |
| goldak | lane-in625-2020 | 14 | 24.2 -> 14.9 | 37.6 -> 39.2 | -24.2 -> -14.9 | -24.1 -> -13.7 |
| goldak | pooled-summary-scope | 745 | 20.2 -> 15.8 | 38.2 -> 41.6 | -17.7 -> -10.6 | 18.8 -> 24.2 |
| goldak | totis-ti64-2021 | 80 | 21.1 -> 20.6 | 37.8 -> 39.1 | -13.3 -> -6.9 | -5.3 -> -2.9 |

Computed rows in the summary scope (before -> after): rosenthal 679 -> 750, eagar-tsai 757 -> 757, goldak 745 -> 753.
