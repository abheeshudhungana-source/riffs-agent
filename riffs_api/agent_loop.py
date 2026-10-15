"""A small observable agent loop for the chord-first RIFFs workflow."""

from __future__ import annotations

from dataclasses import asdict
from io import BytesIO
from typing import Any
from zipfile import ZipFile

from riffs_api.progression import ProgressionError, parse_progression
from riffs_api.prompt_guardrails import PromptRefusal, validate_prompt
from riffs_api.render import render_symbolic_package, symbolic_package_filename
from riffs_api.prompt_intent import resolve_groove
from riffs_api.score import SUPPORTED_INSTRUMENTS, draft_instrument_score, draft_score
from riffs_api.tool_access import ALLOWED_TOOLS, call_tool


class RiffBuildEnvironment:
    """State and allowlisted actions for drafting a symbolic RIFF package."""

    def __init__(self, progression: str, key: str | None, tempo_bpm: int, prompt: str = "", groove: str | None = None, instruments: list[str] | None = None):
        self.progression = progression
        self.key = key
        self.tempo_bpm = tempo_bpm
        self.prompt = prompt
        self.groove, self.groove_source = resolve_groove(prompt, groove)
        self.instruments = instruments or ["bass_guitar", "rhythm_guitar", "drum_kit"]
        if set(self.instruments) - set(SUPPORTED_INSTRUMENTS):
            raise ValueError("Unsupported instrument in requested lanes.")
        self.parsed: dict[str, Any] | None = None
        self.score: dict[str, Any] | None = None
        self.export: dict[str, Any] | None = None
        self.status = "ready"
        self.error: str | None = None
        self.clarification: dict[str, Any] | None = None
        self.flag: str | None = None
        self.refusal_code: str | None = None
        self.alternative: str | None = None
        try:
            validate_prompt(prompt)
        except PromptRefusal as exc:
            self.status = "unsafe_request"
            self.flag = exc.detail
            self.refusal_code = exc.code
            self.alternative = exc.alternative

    def get_state(self) -> dict[str, Any]:
        """Return a JSON-ready snapshot for the policy to inspect."""
        return {
            "status": self.status,
            "done": self.status in {"completed", "failed", "awaiting_input", "refused"},
            "input": {
                "progression": self.progression,
                "key": self.key,
                "tempo_bpm": self.tempo_bpm,
                "groove": self.groove,
                "groove_source": self.groove_source,
                "instruments": self.instruments,
            },
            "parsed_progression": self.parsed,
            "score": self.score,
            "export": self.export,
            "error": self.error,
            "clarification": self.clarification,
            "flag": self.flag,
            "refusal_code": self.refusal_code,
            "alternative": self.alternative,
        }

    def step(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute one allowlisted action and return its result."""
        del args  # Actions currently derive their inputs from observed environment state.
        try:
            if action not in ALLOWED_TOOLS:
                raise PermissionError(f"Action '{action}' is not allowed.")

            if action == "parse_progression":
                parsed = call_tool("parse_progression", "read", progression=self.progression, key=self.key)
                self.parsed = parsed
                self.status = "parsed"
                return {"ok": True, "action": action, "chord_chart": parsed["chord_chart"]}

            if action == "draft_score":
                if self.parsed is None:
                    raise ValueError("Parse the progression before drafting a score.")
                score_data = call_tool(
                    "draft_score", "write",
                    progression=self.progression, key=self.key, tempo_bpm=self.tempo_bpm,
                    groove=self.groove, instruments=self.instruments,
                )
                self.score = score_data
                self.status = "scored"
                return {
                    "ok": True,
                    "action": action,
                    "bar_count": len(score_data["bars"]),
                    "time_signature": score_data["time_signature"],
                }

            if action == "export_symbolic":
                if self.score is None:
                    raise ValueError("Draft a score before exporting it.")
                export_data = call_tool(
                    "export_symbolic", "write",
                    progression=self.progression, key=self.key, tempo_bpm=self.tempo_bpm,
                    prompt=self.prompt, groove=self.groove, instruments=self.instruments,
                )
                self.export = export_data
                self.status = "completed"
                return {"ok": True, "action": action, **self.export}

            raise PermissionError(f"Action '{action}' is not allowed.")
        except (ProgressionError, ValueError, PermissionError) as exc:
            self.status = "parse_failed" if action == "parse_progression" and not isinstance(exc, PermissionError) else "failed"
            self.error = str(exc)
            return {"ok": False, "action": action, "error": self.error}


def observe(env: RiffBuildEnvironment) -> dict[str, Any]:
    return env.get_state()


def decide(state: dict[str, Any], history: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose the next deterministic step from the latest observation."""
    del history  # The current policy is state-driven and has no hidden memory.
    if state["status"] == "unsafe_request":
        return {
            "action": "refuse",
            "args": {
                "reason": state["flag"],
                "alternative": state.get("alternative") or "offer a safe, original progression",
            },
        }
    if state["status"] == "parse_failed":
        return {
            "action": "request_clarification",
            "args": {"reason": state["error"]},
        }
    if state["done"]:
        return {"action": "finish", "args": {}}
    if state["parsed_progression"] is None:
        return {"action": "parse_progression", "args": {}}
    if state["score"] is None:
        return {"action": "draft_score", "args": {}}
    if state["export"] is None:
        return {"action": "export_symbolic", "args": {}}
    return {"action": "finish", "args": {}}


def act(env: RiffBuildEnvironment, decision: dict[str, Any]) -> dict[str, Any]:
    action = decision.get("action")
    if action == "finish":
        return {"ok": True, "action": "finish", "done": True}
    if action == "request_clarification":
        reason = str((decision.get("args") or {}).get("reason") or "Please clarify the progression.")
        env.clarification = {"reason": reason}
        env.status = "awaiting_input"
        return {
            "ok": True,
            "action": action,
            "reason": reason,
            "done": True,
        }
    if action == "refuse":
        args = decision.get("args") or {}
        reason = str(args.get("reason") or "The request is outside RIFFs' instrumental scope.")
        alternative = str(args.get("alternative") or "Offer a safe, original progression.")
        env.flag = reason
        env.alternative = alternative
        env.status = "refused"
        return {
            "ok": True,
            "action": action,
            "reason": reason,
            "alternative": alternative,
            "done": True,
        }
    return env.step(action, decision.get("args") or {})


def run_loop(env: RiffBuildEnvironment, max_steps: int = 5) -> list[dict[str, Any]]:
    """Run observe → decide → act → observe until completion or the step limit."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1.")

    history: list[dict[str, Any]] = []
    for step_number in range(1, max_steps + 1):
        state = observe(env)
        decision = decide(state, history)
        result = act(env, decision)
        state_after = observe(env)
        history.append({
            "step": step_number,
            "state": state,
            "decision": decision,
            "result": result,
            "state_after": state_after,
        })
        if result.get("done") or state_after["done"]:
            break

    if history and not history[-1]["state_after"]["done"]:
        history[-1]["result"] = {
            **history[-1]["result"],
            "step_limit_reached": True,
        }
    return history
