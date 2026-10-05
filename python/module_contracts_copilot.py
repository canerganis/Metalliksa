"""Source-bound inventory of the advisory chat; no scientific oracle."""
from module_contract import (
    Authority, ContractError, Evidence, FORBIDDEN_CLAIM_KEYS, Lifecycle,
    ModuleContract, Operation, Oracle, OutputSchema, OWNER_UNASSIGNED,
    PENDING_ORACLE_CEILING, TestRefs, View,
)


def build_copilot_contract(seed):
    if seed.get("id") != "copilot":
        raise ContractError("copilot requires its own seed")
    local = Authority(kind="browser-local", timeout_ms=None,
                      exception_reason="Draft, transcript and clipboard actions use browser-local state.")
    def action(name, inputs, outputs):
        return Operation(id=name, route=None, method=None, authority=local,
                         undeclared_input=inputs,
                         output=OutputSchema(fields=outputs, status_key=None))
    return ModuleContract(
        id=seed["id"], version="0.1.0", owner=OWNER_UNASSIGNED,
        workspace=seed["workspace"], label=seed["label"], description=seed["description"],
        next=seed["next"], maturity=seed["scope"], navigation="listed",
        view=View(component=seed["viewComponent"], export=seed["viewExport"]),
        migration_state="contracted",
        operations=(
            action("edit-prompt", ("inputPrompt",), ("inputPrompt",)),
            Operation(id="consult", method="POST", route="/api/metallurgy/consult",
                      authority=Authority(kind="node-provider", timeout_ms=60000),
                      undeclared_input=("prompt", "history"),
                      output=OutputSchema(fields=("response", "text", "answer", "error"), status_key=None)),
            action("copy-message", ("id", "text"), ("clipboardWrite", "copiedId")),
            action("clear-history", (), ("messages",)),
        ),
        lifecycle=Lifecycle(background_work="none", resources=("fetch",)),
        evidence=Evidence(emits=(), ceiling=PENDING_ORACLE_CEILING,
                          forbidden_claims=FORBIDDEN_CLAIM_KEYS,
                          note="Language-model prose is advisory, not measured data or solver validation; no grounded scientific oracle is declared."),
        tests=TestRefs(oracle=Oracle(status="pending"), schema="python/test_module_contract_copilot.py",
                       docs="docs/modules/copilot.md"),
        legacy_notes=(
            "The prompt field and five visible suggestion buttons call the same consult action. Suggestions are predefined questions, not canned scientific answers. The initial welcome and cleared-chat messages are UI text.",
            "The view sends prompt and prior role/content history. The current server handler uses prompt/message, optional context and systemInstruction; it does not consume the history array, so transcript display is not proof of conversational context reaching the provider.",
            "The server returns response/text/answer on success. The current view reads reply/text and appends operational errors to its transcript. Missing provider text is not a scientific result. Air-gap refusal and validation/provider errors do not execute a local substitute.",
            "The 60000 ms bound is the provider request deadline, not a browser-side scientific execution time. The current chat fetch has no abort signal or generation gate; clearing history or unmount does not cancel it. This limitation remains explicitly recorded until the product repair is verified.",
            "Clipboard feedback is optimistic: writeText is not awaited and copiedId clears on a 2000 ms timer. Smooth scroll runs when messages/loading change. The UI loading phrase about computing thermodynamic state does not imply a physics solver is invoked.",
        ),
        source_refs=("src/components/MetallurgyCopilot.tsx::MetallurgyCopilot",
                     "routes/copilot.ts", "server/openaiService.ts::generateGpt6Response"),
        seed_derived=("label", "description", "next", "maturity"),
    )
