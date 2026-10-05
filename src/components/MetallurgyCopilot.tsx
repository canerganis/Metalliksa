import React, { useState, useRef, useEffect } from "react";
import {
  Sparkles,
  Send,
  Bot,
  User,
  Lightbulb,
  Trash2,
  Copy,
  Check,
  Flame,
  Atom,
  Shield,
  Layers,
} from "lucide-react";
import { ConsultMessage } from "../types";
import {
  ConsultationResponseError,
  parseConsultationResponse,
} from "../utils/calphadConsultation";
import { CopilotRequestLifecycle, CopyFeedbackLifecycle } from "../utils/copilotConsultation";

export const MetallurgyCopilot: React.FC = () => {
  const [messages, setMessages] = useState<ConsultMessage[]>([
    {
      id: "welcome-1",
      role: "assistant",
      content: `Hello! I am your **AI Pocket Metallurgy & Materials Science Copilot**, powered by GPT-6 Sol.

You can consult me on:
- **Phase Equilibria & Solidification**: Fe-C, Ti-Al, Ni-base phase diagrams, TTT/CCT cooling curves, eutectics, and peritectics.
- **Physical Metallurgy & Strengthening Mechanisms**: Solid solution, precipitation hardening (e.g. Al-Cu GP zones, $\\gamma'-\\text{Ni}_3(\\text{Al,Ti})$), grain boundary Hall-Petch, dislocation density, and work hardening.
- **Heat Treatment & Thermodynamics**: Quench & temper cycles, carburizing/nitriding kinetics, homogenizing, sub-zero cryogenic treatment, and CALPHAD principles.
- **Failure Analysis & Fractography**: Fatigue striations, hydrogen embrittlement (HICC), stress corrosion cracking (SCC), creep rupture, and intergranular sensitization ($M_{23}C_6$).
- **Welding Metallurgy & Additive Manufacturing**: AWS D1.1 preheat calculations, Schaeffler constitution, epitaxial solidification, and LPBF keyhole porosity mitigation.

How can I assist your engineering investigation or alloy formulation today?`,
      timestamp: Date.now(),
    },
  ]);

  const [inputPrompt, setInputPrompt] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [copyFeedback, setCopyFeedback] = useState<{ id: string; state: "copied" | "failed" } | null>(null);
  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const requestLifecycle = useRef(new CopilotRequestLifecycle());
  const copyLifecycle = useRef(new CopyFeedbackLifecycle());
  const mounted = useRef(false);
  const copyFeedbackTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const prefersReducedMotion = typeof window !== "undefined"
      && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;
    chatEndRef.current?.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth" });
  }, [messages, isLoading]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      requestLifecycle.current.invalidate();
      copyLifecycle.current.invalidate();
      if (copyFeedbackTimer.current !== null) clearTimeout(copyFeedbackTimer.current);
    };
  }, []);

  const promptSuggestions = [
    {
      label: "Sensitization of 304 Stainless",
      prompt:
        "Explain the thermodynamic mechanism of sensitization in AISI 304 stainless steel at 500-800°C. Detail chromium carbide (M23C6) precipitation, the depleted chromium zone along grain boundaries, and how 304L and stabilized grades (321 with Ti, 347 with Nb) prevent intergranular corrosion.",
    },
    {
      label: "Al-Cu Precipitation Hardening",
      prompt:
        "Explain the continuous precipitation sequence in Al-4%Cu (2024 alloy) during artificial aging: Solid Solution -> GP-I zones -> GP-II (θ'') -> θ' (Al2Cu) -> equilibrium θ (Al2Cu). Discuss coherency strain and peak hardness.",
    },
    {
      label: "High-Temperature Creep Mechanisms",
      prompt:
        "Contrast Nabarro-Herring lattice diffusion creep, Coble grain boundary diffusion creep, and dislocation power-law climb creep in high-temperature superalloys. How do single-crystal (SX) castings eliminate Coble creep?",
    },
    {
      label: "Nitinol Shape Memory Effect",
      prompt:
        "Describe the crystallographic mechanism of the Shape Memory Effect and Superelasticity in 55-Nitinol (NiTi). Detail the thermoelastic martensitic transformation between parent B2 cubic Austenite and B19' monoclinic Martensite.",
    },
    {
      label: "LPBF 3D Printing Metallurgy",
      prompt:
        "Analyze the microstructural characteristics of Laser Powder Bed Fusion (LPBF) processed Inconel 718 or 316L. Detail columnar grain growth, cellular sub-grain dislocation networks, elemental microsegregation, and residual stress relief.",
    },
  ];

  const handleSendMessage = async (userText: string) => {
    if (!userText.trim() || isLoading) return;
    const request = requestLifecycle.current.begin();

    const userMessage: ConsultMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: userText,
      timestamp: Date.now(),
    };

    const newHistory = [...messages, userMessage];
    setMessages(newHistory);
    setInputPrompt("");
    setIsLoading(true);

    try {
      // Build conversation history format for API
      const apiHistory = newHistory.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await fetch("/api/metallurgy/consult", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: userText,
          history: apiHistory.slice(0, -1), // prior history
        }),
        signal: request.signal,
      });

      const rawText = await res.text();
      let data: unknown;
      try {
        data = JSON.parse(rawText);
      } catch {
        throw new Error(res.ok ? "The consultation service returned invalid data." : `Consultation service unavailable (HTTP ${res.status}).`);
      }

      if (!res.ok) {
        const detail = data && typeof data === "object" && "error" in data && typeof data.error === "string"
          ? data.error.trim()
          : "";
        throw new Error(detail || `Consultation request failed (HTTP ${res.status}).`);
      }

      const answer = parseConsultationResponse(data);

      const assistantMessage: ConsultMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        content: answer,
        timestamp: Date.now(),
      };

      if (requestLifecycle.current.isCurrent(request)) {
        setMessages((prev) => [...prev, assistantMessage]);
      }
    } catch (err: unknown) {
      if (!requestLifecycle.current.isCurrent(request)) return;
      const errorMessage: ConsultMessage = {
        id: `error-${Date.now()}`,
        role: "assistant",
        content: err instanceof ConsultationResponseError
          ? "Consultation unavailable: the service returned no usable answer text."
          : `Consultation error: ${err instanceof Error ? err.message : "Failed to communicate with the consultation service."}`,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      if (requestLifecycle.current.isCurrent(request)) setIsLoading(false);
    }
  };

  const handleCopy = async (id: string, text: string) => {
    const generation = copyLifecycle.current.begin();
    if (copyFeedbackTimer.current !== null) clearTimeout(copyFeedbackTimer.current);
    setCopyFeedback(null);
    try {
      if (typeof navigator === "undefined" || !navigator.clipboard?.writeText) {
        throw new Error("Clipboard access is unavailable.");
      }
      await navigator.clipboard.writeText(text);
      if (!mounted.current || !copyLifecycle.current.isCurrent(generation)) return;
      setCopyFeedback({ id, state: "copied" });
      copyFeedbackTimer.current = setTimeout(() => {
        if (mounted.current && copyLifecycle.current.isCurrent(generation)) {
          setCopyFeedback(null);
          copyFeedbackTimer.current = null;
        }
      }, 2000);
    } catch {
      if (mounted.current && copyLifecycle.current.isCurrent(generation)) setCopyFeedback({ id, state: "failed" });
    }
  };

  const handleClearHistory = () => {
    requestLifecycle.current.invalidate();
    copyLifecycle.current.invalidate();
    setIsLoading(false);
    setCopyFeedback(null);
    if (copyFeedbackTimer.current !== null) {
      clearTimeout(copyFeedbackTimer.current);
      copyFeedbackTimer.current = null;
    }
    setMessages([
      {
        id: "welcome-reset",
        role: "assistant",
        content: "Chat history cleared. How can I assist your metallurgical calculations or alloy inquiry?",
        timestamp: Date.now(),
      },
    ]);
  };

  return (
    <div id="metallurgy-copilot-container" className="space-y-3.5 max-w-5xl mx-auto">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl bg-[#090e18] border border-[#162032]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-sky-500/20 border border-sky-400/40 flex items-center justify-center text-sky-400">
            <Sparkles className="w-4 h-4 text-sky-400" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-white tracking-tight font-mono">AI Metallurgy & Materials Science Copilot</h2>
            <p className="text-xs text-slate-400">
              Language-model answers to metallurgy questions; advisory only, verify every claim against sources.
            </p>
          </div>
        </div>

        <button
          onClick={handleClearHistory}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#0c1322] hover:bg-white/5 text-slate-400 hover:text-white border border-[#162032] text-xs font-mono transition motion-reduce:transition-none self-start md:self-auto"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Clear Chat</span>
        </button>
      </div>

      {/* Quick Prompts Bar */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest flex items-center gap-1">
          <Lightbulb className="w-3 h-3 text-sky-400" />
          Specialized Engineering Query Presets:
        </span>
        <div className="flex gap-2 overflow-x-auto pb-1 max-w-full">
          {promptSuggestions.map((item, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(item.prompt)}
              className="px-2.5 py-1 bg-[#090e18] hover:bg-white/5 border border-[#162032] hover:border-sky-400/50 rounded text-xs text-slate-300 hover:text-sky-300 transition motion-reduce:transition-none whitespace-nowrap shrink-0 font-mono"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Messages Log */}
      <div className="bg-[#090e18] rounded-xl border border-[#162032] p-4 md:p-5 min-h-[480px] max-h-[580px] overflow-y-auto space-y-3.5">
        {messages.map((msg) => {
          const isUser = msg.role === "user";
          return (
            <div
              key={msg.id}
              className={`flex items-start gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
            >
              {/* Avatar */}
              <div
                className={`w-7 h-7 rounded flex items-center justify-center shrink-0 text-xs ${
                  isUser
                    ? "bg-cyan-500/20 border border-cyan-500/40 text-cyan-300"
                    : "bg-sky-500/20 border border-sky-400/40 text-sky-400"
                }`}
              >
                {isUser ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5" />}
              </div>

              {/* Message Bubble */}
              <div
                role={msg.id.startsWith("error-") ? "alert" : undefined}
                aria-live={msg.id.startsWith("error-") ? "assertive" : undefined}
                className={`max-w-[85%] rounded-lg p-3.5 text-xs leading-relaxed border relative group ${
                  isUser
                    ? "bg-sky-950/40 border-sky-800/60 text-sky-100 rounded-tr-none"
                    : "bg-[#0c1322] border-[#162032] text-slate-200 rounded-tl-none font-sans"
                }`}
              >
                <div className="whitespace-pre-line space-y-1.5">{msg.content}</div>

                {/* Timestamp & Copy Button */}
                <div className="flex items-center justify-between mt-2.5 pt-1.5 border-t border-[#162032] text-[10px] font-mono text-slate-500">
                  <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                  <button
                    onClick={() => handleCopy(msg.id, msg.content)}
                    aria-label={copyFeedback?.id === msg.id
                      ? copyFeedback.state === "copied" ? "Copied to clipboard" : "Clipboard unavailable"
                      : "Copy message"}
                    className="opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-400 transition motion-reduce:transition-none text-slate-400 hover:text-white flex items-center gap-1"
                  >
                    {copyFeedback?.id === msg.id && copyFeedback.state === "copied" ? (
                      <>
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span className="text-emerald-400" role="status" aria-live="polite">Copied</span>
                      </>
                    ) : copyFeedback?.id === msg.id && copyFeedback.state === "failed" ? (
                      <span className="text-amber-300" role="status" aria-live="polite">Copy unavailable</span>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        <span>Copy</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div role="status" aria-live="polite" aria-atomic="true" className="flex items-start gap-2.5">
            <div className="w-7 h-7 rounded bg-sky-500/20 border border-sky-400/40 flex items-center justify-center shrink-0 text-sky-400">
              <Bot className="w-3.5 h-3.5" />
            </div>
            <div className="bg-[#0c1322] border border-[#162032] rounded-lg rounded-tl-none p-3 text-xs text-slate-400 flex items-center gap-2 font-mono">
              <div aria-hidden="true" className="w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin motion-reduce:animate-none"></div>
              <span>Waiting for an advisory response from the consultation service…</span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* Input Field */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (typeof navigator !== "undefined" && navigator.vibrate) {
            navigator.vibrate(10);
          }
          handleSendMessage(inputPrompt);
        }}
        className="flex gap-2 p-1.5 bg-[#090e18] rounded-xl border border-[#162032]"
      >
        <input aria-label="Ask the copilot"
          type="text"
          value={inputPrompt}
          onChange={(e) => setInputPrompt(e.target.value)}
          placeholder="Ask about phase diagrams, heat treatments, fracture modes, alloy design..."
          disabled={isLoading}
          className="flex-1 bg-transparent px-3 py-2 text-sm sm:text-xs text-white placeholder-slate-500 focus:outline-none font-sans"
        />
        <button
          type="submit"
          disabled={isLoading || !inputPrompt.trim()}
          className="px-4 py-2 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold rounded text-xs flex items-center gap-1.5 shadow-[0_0_12px_rgba(56,189,248,0.3)] transition motion-reduce:transition-none disabled:opacity-40 font-mono active:scale-95 motion-reduce:active:scale-100"
        >
          <span>Consult</span>
          <Send className="w-3.5 h-3.5" />
        </button>
      </form>
    </div>
  );
};
