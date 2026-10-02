# NIST access and suitability review — 2026-10-02

Evidence scope: official dataset metadata was acquired from the NIST PDR using
`https://data.nist.gov/od/id/<id>?format=nerdm`. The four original response files
are retained with byte counts and locally calculated SHA-256 in `manifest.json`.
The embedded NIST `components[].checksum.hash` and `size` describe the payloads;
they do not prove that those payloads were downloaded. No new measurement payload
was acquired in this review. TLS verification stayed enabled.

## Current official inventory

| Dataset | Version | Downloadable entries | Advertised bytes | Usefulness for current solver |
|---|---|---:|---:|---|
| mds2-2715 | 1.0.2 | 25 | 261,017,036,265 | IN718 3D build thermography; MATLAB Temperature/TAM/SCR processing scripts are a useful first target. Full validation needs build geometry, layer history, spatial registration and a matching observation operator. |
| mds2-2716 | 1.3.1 | 8 | 1,159,428,413 | Closest experiment: IN718 bare-plate tracks/pads. The local Signal, XYPT and README files still match current official hashes. Remaining microscopy surface images do not repair the temperature conversion ambiguity. |
| mds2-3842 | 1.0.3 | 3 | 101,531 | Dynamic coupling time series and process summary. Coupling includes plume interactions and cannot be substituted for material absorptivity. No uncertainty budget is supplied by the dataset description. |
| mds2-4103 | 1.0.0 | 546 | 38,536,588,265 | IN718 pad cross sections, powder thickness and turn-around variation. Small measured width/depth/overlap/area CSVs exist; useful after matching pad history and defining a pad observation operator. Not a drop-in single-track holdout. |

Counts include checksum sidecars where published and differ from older harvested
Data.gov entries (2715 currently advertises 25 downloadable entries, not 29).
The NIST metadata contain no `accessURL`, S3 origin or alternate payload mirror.

## Access evidence

- Additional public record checked: [mds2-3707](https://data.nist.gov/od/id/mds2-3707), version 1.1 (revised 2025-12-11), 51 files and 38.30 GB advertised. It contains AMB2025-06/07 IN718 calibration inputs and single-track melt-pool cross-sections. This is potentially useful for calibration after matching process conditions and defining the image observation operator; it is not an independent holdout.
- The 29.2 kB `20241010_AMB_SL_1_mask.tif` direct link timed out after 30 seconds with zero bytes. No payload was retained; see `alternate-access-log.json` and `manifest.json`.

- Sandbox requests fail at the configured loopback proxy. Approved network reads
  obtained HTTP 200 for `/rmm/records/mds2-2715` and all four `?format=nerdm` URLs.
- Approved payload requests for the 2715 README and two MATLAB scripts timed out
  at 25/30 seconds. `acquisition-log.json` records the two MATLAB failures.
- Both short-id and ARK-form HEAD requests for 3842's summary CSV timed out at
  15 seconds with zero bytes. A bounded parallel attempt for 4103's
  `SampleIParameters.csv`, 3842's summary CSV, and its `/_aip/_head` archive API
  timed out at 12 seconds each. `alternate-access-log.json` retains these results.
- The parent agent independently observed Cloudflare HTTP 524 in the browser for
  the NIST README. This supports a distribution-host timeout; metadata access is
  working. No absent-publication inference is warranted.
- NIST's public distribution-service source supports file and bundle endpoints;
  it does not disclose a usable storage mirror in the acquired metadata. No
  signed URL, credentials, or private storage access was attempted.

## Current local 2716 bytes rechecked against official v1.3.1

| File | Bytes | SHA-256 |
|---|---:|---|
| `AMB2022-03-718-AMMT-StaringCamera_Signal.h5` | 549979044 | f6fe21ec911707f72e7efda2932c77eae2b75d84765848878fe5beb6b728cd43 |
| `AMB2022-03-AMMT-718-Pad_XYPT.h5` | 406992 | 7b7004753e150bc26632e9ce356e0440429160fa92cbff8fc8559202fdce2103 |
| local `README.txt` / official `2716_README.txt` | 12573 | ba44076ed51b69c0e4ca80ff0e2568eed2dc6459e85c9ad83b85860bee5760f2 |

The calibration obstacle is `/Calibration/ThermalCal` attribute `Model`:
`T(x) = 14388/a/log((c*e/x+1)-b/a;`. Parentheses are unbalanced and emissivity
`e` is not fixed. The local metadata review records this literal text and leaves
`temperature_conversion` null; it does not execute it. This is an observation
conversion limitation, not a demonstrated thermal-solver runtime failure.
The identical current official Signal checksum means a re-download would not
resolve this string. 2715's MATLAB temperature script could help establish the
intended equation but its applicability to the different experiment, calibration
coefficients and emissivity must be reviewed before conversion.

## Next useful acquisition

0. Retry the `mds2-3707` readme and selected mask/cross-section components through a responsive NIST distribution route; inspect calibration inputs and the image measurement definition before fitting solver parameters.

1. 2715 `2715_README.txt`, `AMB2022_HDF5_Temperature_v1.m`, TAM/SCR scripts.
2. 4103 `4103_ReadMe.txt`, `SampleIParameters.csv`, small measured width/depth,
   overlap and layer-area CSVs; then define case-grouped calibration/holdout.
3. 3842's 101,531-byte complete package, for a coupled-power study with the
   dataset's stated measurement limitations retained.

Do not fetch 2715's 20–119 GB raw HDF5 files until a matching experiment and
operator make their benefit concrete. NIST residual stays unavailable and the
solver remains unvalidated. Metadata acquisition alone is not validation.

Sources: [NIST developer API guidance](https://www.nist.gov/metis/developer-tools),
[2715](https://data.nist.gov/od/id/mds2-2715),
[2716](https://data.nist.gov/od/id/mds2-2716),
[3842](https://data.nist.gov/od/id/mds2-3842),
[4103](https://data.nist.gov/od/id/mds2-4103),
[NIST distribution-service source](https://github.com/usnistgov/oar-dist-service).
