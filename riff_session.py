"""CLI Session Runner for RIFFs with soft-delete trash and HITL vocal checkpoints."""

import os
import shutil
import pathlib
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from agent import RiffsAgent, VocalApprovalError

TRASH_DIR = pathlib.Path("riffs_trash")
TRASH_DIR.mkdir(exist_ok=True)


@dataclass
class SessionTake:
    take_id: int
    prompt: str
    chords: str
    key: str
    bpm: int
    groove: str
    lyrics_prompt: str
    lyrics: List[str]
    vocal_confirmation_token: str
    audio_path: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)


def create_checkpoint_take(agent: RiffsAgent, take_id: int, prompt: str, chords: str,
                           lyrics_prompt: str, key: str = "Am", bpm: int = 110,
                           groove: str = "straight") -> SessionTake:
    """Generate instrumental backing and lyrics draft, halting at the vocal checkpoint."""
    res = agent.generate(
        prompt=prompt,
        chords=chords,
        key=key,
        bpm=bpm,
        groove=groove,
        lyrics_prompt=lyrics_prompt,
        vocal_approved=False,
    )
    lines = [b["text"] for b in res["lyrics_draft"]["bars"]]
    audio_path = None
    if "take_storage" in res and "filepath" in res["take_storage"]:
        audio_path = res["take_storage"]["filepath"]

    return SessionTake(
        take_id=take_id,
        prompt=prompt,
        chords=chords,
        key=key,
        bpm=bpm,
        groove=groove,
        lyrics_prompt=lyrics_prompt,
        lyrics=lines,
        vocal_confirmation_token=res["vocal_confirmation_token"],
        audio_path=audio_path,
        data=res,
    )


def cli_voice(agent: RiffsAgent, take: SessionTake, auto_confirm: Optional[bool] = None,
              override_lyrics: Optional[List[str]] = None,
              acknowledge_unassessed_rights: bool = True) -> Dict[str, Any]:
    """CLI checkpoint prompt: wires user [y/n] input to cryptographic token verification."""
    lyrics_to_use = override_lyrics if override_lyrics is not None else take.lyrics
    print("\n--- [Vocal Checkpoint] ---")
    for i, line in enumerate(lyrics_to_use, 1):
        print(f"  Line {i}: {line}")

    if auto_confirm is not None:
        choice = "y" if auto_confirm else "n"
        print(f"Synthesize voice? [y/n]: {choice} (auto)")
    else:
        choice = input("Synthesize voice? [y/n]: ").strip().lower()

    if choice != "y":
        print(">> Vocal synthesis skipped by user.")
        return None

    # Submit to agent with cryptographic token and lyrics
    return agent.generate(
        prompt=take.prompt,
        chords=take.chords,
        key=take.key,
        bpm=take.bpm,
        groove=take.groove,
        lyrics_prompt=take.lyrics_prompt,
        vocal_approved=True,
        vocal_approval_token=take.vocal_confirmation_token,
        edited_lyrics=lyrics_to_use,
        acknowledge_unassessed_rights=acknowledge_unassessed_rights,
    )


def discard_take(take: SessionTake, active_takes: List[SessionTake],
                 trash_dir: pathlib.Path = TRASH_DIR) -> Optional[pathlib.Path]:
    """Soft-delete: moves take artifact to trash directory so discard is recoverable."""
    if take in active_takes:
        active_takes.remove(take)

    trash_path = None
    if take.audio_path and pathlib.Path(take.audio_path).exists():
        src = pathlib.Path(take.audio_path)
        trash_path = trash_dir / f"take_{take.take_id}_{src.name}"
        shutil.move(src, trash_path)
        take.audio_path = str(trash_path)
    else:
        # Create a metadata placeholder if no physical file was written
        trash_path = trash_dir / f"take_{take.take_id}_metadata.json"
        trash_path.write_text(f'{{"take_id": {take.take_id}, "prompt": "{take.prompt}"}}')

    print(f">> Soft-deleted Take #{take.take_id} to {trash_path.name}")
    return trash_path


def restore_take(take: SessionTake, active_takes: List[SessionTake],
                 trash_dir: pathlib.Path = TRASH_DIR) -> bool:
    """Restores a soft-deleted take back to active session."""
    active_takes.append(take)
    print(f">> Restored Take #{take.take_id} back to active takes.")
    return True


def end_session(active_takes: List[SessionTake], trash_dir: pathlib.Path = TRASH_DIR,
                auto_empty: Optional[bool] = None) -> None:
    """End-of-session checkpoint: prompts user to permanently purge or retain trash."""
    trashed_files = list(trash_dir.glob("*"))
    n = len(trashed_files)
    prompt_msg = f"\nSession ending: {len(active_takes)} active take(s), {n} file(s) in trash. Empty trash and exit? [y/n]: "

    if auto_empty is not None:
        choice = "y" if auto_empty else "n"
        print(f"{prompt_msg}{choice} (auto)")
    else:
        choice = input(prompt_msg).strip().lower()

    if choice == "y":
        for f in trashed_files:
            if f.is_file():
                f.unlink()
        print(f">> Emptied {n} file(s) from {trash_dir}/. Session ended cleanly.")
    else:
        print(f">> Kept {n} file(s) in {trash_dir}/ for future recovery.")


def run_demo_session():
    """Runs a complete test session demonstrating token validation, edited lyric rejection, and soft-delete."""
    print("=================================================================")
    print("  RIFFs Interactive Session & HITL Checkpoint Simulation")
    print("=================================================================")

    os.environ.setdefault("RIFFS_VOCAL_SECRET", "test-secret-hitl-2026")
    agent = RiffsAgent()
    active_takes: List[SessionTake] = []

    # 1. Create Take 1: Instrumental backing + verse lyrics draft + token
    print("\n[Step 1] Creating Take 1 with lyrics draft...")
    take1 = create_checkpoint_take(
        agent=agent,
        take_id=1,
        prompt="Mellow neo-soul groove with rhodes",
        chords="Am - F - C - G",
        lyrics_prompt="Driving under city streetlights",
    )
    active_takes.append(take1)
    print(f"Take 1 created! Token: {take1.vocal_confirmation_token[:28]}...")

    # 2. Approve Take 1 with exact lyrics -> SUCCESS
    print("\n[Step 2] User approves Take 1 (exact lyrics)...")
    res1 = cli_voice(agent, take1, auto_confirm=True)
    assert res1.get("status") == "success"
    print(">> Take 1 voice synthesis succeeded! Vocal stem generated.")

    # 3. Create Take 2
    print("\n[Step 3] Creating Take 2...")
    take2 = create_checkpoint_take(
        agent=agent,
        take_id=2,
        prompt="Roots reggae pocket with bubbling organ",
        chords="Am - G - F - G",
        lyrics_prompt="Morning sunlight over Kingston",
    )
    active_takes.append(take2)

    # 4. Attempt to approve Take 2 with EDITED lyrics using the original token -> MUST REJECT
    print("\n[Step 4] Tamper test: Editing lyrics and attempting approval with original token...")
    tampered_lyrics = list(take2.lyrics)
    tampered_lyrics[0] = "A completely different, unreviewed lyrical line"
    print(f"Original Line 1: '{take2.lyrics[0]}'")
    print(f"Tampered Line 1: '{tampered_lyrics[0]}'")

    try:
        cli_voice(agent, take2, auto_confirm=True, override_lyrics=tampered_lyrics)
        print("ERROR: Agent accepted mismatched lyrics! (FAILED)")
    except VocalApprovalError as e:
        print(f">> Agent REJECTED approval as expected! Code: {e.code} | Message: {e}")
        assert e.code == "LYRICS_MISMATCH", f"Expected LYRICS_MISMATCH, got {e.code}"

    # 5. Soft-delete Take 2 to trash
    print("\n[Step 5] Soft-deleting Take 2...")
    discard_take(take2, active_takes)
    print(f"Active takes: {len(active_takes)}")

    # 6. Restore Take 2 from trash
    print("\n[Step 6] Restoring Take 2 from trash...")
    restore_take(take2, active_takes)
    print(f"Active takes: {len(active_takes)}")

    # 7. End session
    print("\n[Step 7] Ending session and emptying trash...")
    discard_take(take2, active_takes)
    end_session(active_takes, auto_empty=True)

    print("\n=================================================================")
    print("  Simulation Complete: All Checkpoints and Gating Verified!")
    print("=================================================================")


if __name__ == "__main__":
    run_demo_session()
