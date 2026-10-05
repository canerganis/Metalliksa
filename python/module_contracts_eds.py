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
            fields=("points", "parserMetadata", "sourceRecord", "sha256", "archiveState", "importError"),
            undeclared=("fileName", "mediaType", "bytes"),
        ),
        _local_operation(
            "restore-latest-source",
            fields=("points", "sourceRecord", "sha256", "restoreState"),
        ),
        _local_operation(
            "identify-peak-candidates",
            fields=("peaks", "background", "parameters"),
            input_fields=(fwhm,),
            undeclared=("spectrumPoints",),
        ),
        _local_operation(
            "export-parsed-csv",
            fields=("csvBlob", "downloadStarted"),
        ),
        _local_operation(
            "download-original-source",
            fields=("sourceBytes", "downloadStarted"),
        ),
        _local_operation(
            "import-vendor-quantification",
            fields=("rows", "errors", "warnings", "totalWeightPct", "composition", "provenance", "accepted"),
            undeclared=(
                "fileName",
                "bytes",
                "instrument",
                "software",
                "analysisType",
            ),
        ),
        _local_operation(
            "send-vendor-composition",
            fields=("callbackInvoked", "composition", "transferProvenance"),
            undeclared=("onSendToAlloyBuilder",),
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
            docs="src/components/EDSSpectrumLab.tsx",
        ),
        migration_state="contracted",
        lifecycle=Lifecycle(background_work="none"),
        legacy_notes=(
            "Browser-local operations have no server route or declared timeout.",
            "Spectrum parse failure is surfaced as an import error; archive failure leaves parsed data usable with persistence failed.",
            "Latest-source restore reports empty or failed storage state; recovered records are hash-verified before parsing.",
            "Peak line matching is candidate listing only and must not be interpreted as elemental quantification.",
            "Vendor-import metadata is required for acceptance; invalid tables are not transferable.",
            "Object URLs used by exports and original-source downloads are revoked after the click.",
            "Nested request values: spectrum points are arrays of {energyKeV, counts}; source and vendor file bytes are ArrayBuffer values; vendor metadata keys are strings, with analysisType spot or area.",
            "Composition transfer requires an available optional onSendToAlloyBuilder callback and an accepted vendor quantification result.",
        ),
        source_refs=(
            "python/module_registry_seed.json:143-151",
            "src/components/EDSSpectrumLab.tsx:75-216",
            "src/components/EDSSpectrumLab.tsx:233-268",
            "src/utils/edsParser.ts:45-131",
            "src/utils/edsPeakId.ts:1-6",
            "src/utils/edsPeakId.ts:343-450",
            "src/utils/edsVendorQuant.ts:21-78",
            "src/utils/edsVendorQuant.ts:101-223",
            "src/utils/edsSourceArchive.ts:8-95",
        ),
        seed_derived=("label", "description", "next", "maturity"),
    )
