"""Synthetic contract test for UE Actor/Mass behavior-log ingestion."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from evaluate_ue_behavior_tiers import load_tier_sequences


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        session = Path(tmp)
        actor = session / "agent_p001_test.jsonl"
        actor.write_text("\n".join([
            json.dumps({"event": "session_start", "persona_id": 1, "policy_mode": "HybridPCSP", "active_ablation": "full"}),
            json.dumps({"event": "decision", "persona_id": 1, "policy_action_index": 6, "pos": [0, 0], "needs": [0.8] * 8}),
            json.dumps({"event": "decision", "persona_id": 1, "logits": [0] * 7 + [1] + [0] * 12, "pos": [0, 0], "needs": [0.7] * 8}),
        ]), encoding="utf-8")
        (session / "mass_trajectories.jsonl").write_text("\n".join([
            json.dumps({"persona_id": 1, "stable_index": 0, "policy_action_index": 6, "pos": [0, 0], "needs": [0.8] * 8}),
            json.dumps({"persona_id": 1, "stable_index": 0, "policy_action_index": 7, "pos": [0, 0], "needs": [0.7] * 8}),
        ]), encoding="utf-8")
        sequences, meta = load_tier_sequences(session)
        assert len(sequences["actor"][1]) == 2
        assert len(sequences["mass"][1]) == 2
        assert meta == {"active_ablation": "full", "policy_mode": "HybridPCSP"}
    print("UE behavior tier adapter contract PASS")


if __name__ == "__main__":
    main()
