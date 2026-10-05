"""Source-bounded SDK contract for the browser-local EDS Spectrum Lab."""
from __future__ import annotations

from typing import Mapping

from module_contract import (
    FORBIDDEN_CLAIM_KEYS,
    OWNER_UNASSIGNED,
    Authority,
    Evidence,
    InputField,
    Lifecycle,
    ModuleContract,
    Operation,
    Oracle,
    OutputSchema,
    TestRefs,
    View,
)


_LOCAL = Authority(
    kind="browser-local",
    exception_reason=(
        "EDSSpectrumLab uses browser File APIs, local EDS utilities, IndexedDB source storage, "
        "and an optional parent callback; no server operation or deadline is declared."
    ),
)


def _local_operation(
    operation_id: str,
    *,
    fields: tuple[str, ...],
    undeclared: tuple[str, ...] = (),
    input_fields: tuple[InputField, ...] = (),
) -> Operation:
    return Operation(
        id=operation_id,
        route=None,
        method=None,
        authority=_LOCAL,
        input=input_fields,
        undeclared_input=undeclared,
        output=OutputSchema(fields=fields, status_key=None),
    )


def build_eds_contract(seed: Mapping[str, str]) -> ModuleContract:
    """Build a contracted description from the canonical EDS seed identity."""
    fwhm = InputField(
        key="fwhmEv",
        label="Detector FWHM",
        unit="eV",
        quantity_kind="energy_resolution",
        min=20.0,
        max=1000.0,
        default=130.0,
        required=False,
        note="Optional peak-search setting; the UI falls back to 130 eV when the value is out of range.",
    )
    operations = (
        _local_operation(
            "import-spectrum",
            fields=("uploadedSpectrum", "importError", "sourceRestoreState"),
            undeclared=("file",),
        ),
        _local_operation(
            "restore-latest-source",
            fields=("uploadedSpectrum", "sourceRestoreState"),
        ),
        _local_operation(
            "identify-peak-candidates",
            fields=("peaks", "background", "parameters"),
            input_fields=(fwhm,),
            undeclared=("uploadedSpectrum",),
        ),
        _local_operation(
            "export-parsed-csv",
            fields=("blob", "url", "anchor"),
            undeclared=("uploadedSpectrum",),
        ),
        _local_operation(
            "download-original-source",
            fields=("url", "anchor"),
            undeclared=("uploadedSpectrum",),
        ),
        _local_operation(
            "import-vendor-quantification",
            fields=("rows", "errors", "warnings", "totalWeightPct", "composition", "provenance", "transferLabel", "accepted"),
            undeclared=(
                "vendorFile",
                "vendorInstrument",
                "vendorSoftware",
                "vendorAnalysisType",
            ),
        ),
        _local_operation(
            "send-vendor-composition",
            fields=("composition", "transfer"),
            undeclared=("vendorCurrent", "vendorResult", "onSendToAlloyBuilder"),
        ),
    )
    return ModuleContract(
        id="eds-lab",
        version="1.0.0",
        owner=OWNER_UNASSIGNED,
        workspace=seed["workspace"],
        label=seed["label"],
        description=seed["description"],
        next=seed["next"],
        maturity=seed["scope"],
        navigation="listed",
        view=View(component=seed["viewComponent"], export=seed["viewExport"]),
        operations=operations,
        evidence=Evidence(
            emits=(),
            ceiling="screening-only",
            forbidden_claims=FORBIDDEN_CLAIM_KEYS,
            note=(
                "Peak identification reports spectrum maxima and nearby tabulated line candidates; it does not "
                "produce quantitative composition. Composition transfer is limited to accepted vendor-reported "
                "quantification and retains its provenance; it is not bulk composition. No independent oracle "
                "promotes these outputs beyond screening-only. Parse, archive, restore, or storage failures are "
                "operational outcomes, not scientific evidence statuses."
            ),
        ),
        tests=TestRefs(
            oracle=Oracle(status="pending"),
            schema="python/test_module_contract_eds.py",
            docs="docs/modules/eds-lab.md",
        ),
        migration_state="contracted",
        lifecycle=Lifecycle(background_work="none", resources=("raf",)),
        legacy_notes=(
            "Browser-local operations have no server route or declared timeout; file selection and component mount are their triggers, while export and source download consume current uploadedSpectrum state.",
            "File inputs are browser File objects read through arrayBuffer(); parsed spectrum state is the parser result plus source metadata, and parse failure is surfaced in importError.",
            "Nested values: uploadedSpectrum.points is an array of {energyKeV: number, counts: number}; source and vendor file bytes are ArrayBuffer values; vendor metadata is held in instrument, software, and analysisType strings, with accepted analysis types spot and area.",
            "Browser download handlers return void; export output fields name the actual Blob, object URL, and anchor used for the download, while composition-transfer output fields name the composition and transfer payload passed to the callback or shared-store update.",
            "Source bytes are stored in browser IndexedDB through idb-keyval with SHA-256 content keys and read-back verification; archive failure leaves parsed data usable with sourceRestoreState failed.",
            "Latest-source restore is started on component mount; unmount suppresses later state writes but does not cancel the IndexedDB reads, SHA-256 verification, or parsing already in progress.",
            "Peak line matching is candidate listing only and must not be interpreted as elemental quantification.",
            "Vendor-import metadata is required for acceptance; invalid tables are not transferable.",
            "Exports create a Blob and object URL, click an anchor, then revoke the URL; original-source downloads use the current uploadedSpectrum source bytes and follow the same URL cleanup.",
            "Composition transfer requires vendorCurrent, an accepted vendorResult with provenance and transferLabel; it calls the optional onSendToAlloyBuilder callback when present, otherwise updates the shared material specimen store.",
            "The child WebGLSpectrometerCanvas owns a visibility-aware requestAnimationFrame loop that is cancelled on hide or unmount and deletes its WebGL program on unmount; the loop is the declared raf resource, while browser storage and File APIs have no matching lifecycle vocabulary entry.",
            "The visibility-aware frame hook starts and stops rendering with workspace visibility; this contract does not claim cancellation of in-flight browser storage work or disposal of every replaced WebGL buffer.",
        ),
        source_refs=(
            "python/module_registry_seed.json",
            "src/components/EDSSpectrumLab.tsx::EDSSpectrumLab",
            "src/components/WebGLSpectrometerCanvas.tsx::WebGLSpectrometerCanvas",
            "src/hooks/useVisibleAnimationFrame.ts::useVisibleAnimationFrame",
            "src/utils/edsParser.ts::parseRawEDSFile",
            "src/utils/edsPeakId.ts::findEdsPeaks",
            "src/utils/edsVendorQuant.ts::importVendorQuant",
            "src/utils/edsSourceArchive.ts::archiveEDSSource",
            "src/utils/edsSourceArchive.ts::restoreLatestEDSSource",
            "src/utils/edsSourceArchive.ts::sha256Bytes",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
