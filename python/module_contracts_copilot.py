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
                      undeclared_input=("prompt", "history", "message", "context", "systemInstruction"),
                      output=OutputSchema(fields=("response", "text", "answer", "error"), status_key=None)),
            action("copy-message", ("id", "text"), ("clipboardWrite", "copyFeedback")),
            action("clear-history", (), ("messages", "isLoading", "copyFeedback")),
        ),
        lifecycle=Lifecycle(background_work="none", resources=("fetch",)),
        evidence=Evidence(emits=(), ceiling=PENDING_ORACLE_CEILING,
                          forbidden_claims=FORBIDDEN_CLAIM_KEYS,
                          note="Language-model prose is advisory, not measured data or solver validation; no grounded scientific oracle is declared."),
        tests=TestRefs(oracle=Oracle(status="pending"), schema="python/test_module_contract_copilot.py",
                       docs="docs/modules/copilot.md"),
        legacy_notes=(
            "The prompt field and five visible suggestion buttons call the same consult action. Suggestions are predefined questions, not canned scientific answers. The initial welcome and cleared-chat messages are UI text.",
            "The view sends prompt and prior role/content history. The server handler validates the history array (role user/assistant, string content; malformed entries are a 400) and forwards at most the 20 most recent turns / 50,000 characters to the provider, dropping the oldest first; transcript display older than that window is not proof of context reaching the provider.",
            "The server returns response/text/answer on success. The shared parser accepts nonempty answer text and the view appends operational errors to its transcript. Missing provider text is not a scientific result. Air-gap refusal and validation/provider errors do not execute a local substitute.",
            "The 60000 ms bound is the provider request deadline, not a browser-side scientific execution time. Clearing history, starting a newer request or unmount invalidates the generation and aborts the fetch. Result, error and loading writes are guarded against stale completions.",
            "The current view sends prompt/history only. The route additionally accepts message, context and systemInstruction; prompt/message length is capped at 8000 characters, systemInstruction at 2000 and serialized context at 50000. These free-text/nested keys are recorded as undeclared because InputField cannot enforce string length or context-object shape; handler validation is the authority.",
            "Clipboard feedback awaits writeText and shows failure when unavailable; success feedback clears on a 2000 ms timer. Separate copy-generation guards reject success/failure after clear-history, unmount or a newer copy; the timer is cleared on those actions. The loading phrase says advisory response, not physics computation; scrolling and the spinner respect reduced motion.",
        ),
        source_refs=("src/components/MetallurgyCopilot.tsx::MetallurgyCopilot",
                     "src/utils/copilotConsultation.ts:9-29#export class CopilotRequestLifecycle",
                     "src/utils/copilotConsultation.ts:32-47#export class CopyFeedbackLifecycle",
                     "routes/copilot.ts", "server/openaiService.ts::generateGpt6Response"),
        seed_derived=("label", "description", "next", "maturity"),
    )
