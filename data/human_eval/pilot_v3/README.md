# Human-Eval Pilot Package

Use `participant_packets/pilot_XX.md` for pilot collection.
Fill `pilot_response_template.csv` with each participant's A/B response, confidence, and response time.
Score filled responses with:

```bash
conda run -n paper python src/eval/human_eval.py --csv data/human_eval/pilot_v3/pilot_response_template.csv --answer_key data/human_eval/pilot_v3/pilot_answer_key.csv --output results/eval/human_eval_pilot_summary.json
```

Design: each participant sees all 30 trajectory items once, split 15 rich / 15 coarse.
Across 10 participants, each item is assigned to rich 5 times and coarse 5 times.
