# NPC 페르소나 식별 평가

이 파일은 더 이상 synthetic trace 설문을 담지 않습니다.

논문에 사용할 human evaluation 설문은 실제 평가 대상 모델의 rollout에서 생성해야 합니다. 먼저 PCSP full, ablation, baseline 등 논문에 보고할 모델의 held-out persona rollout을 다음 형식으로 저장한 뒤 설문을 재생성합니다.

```json
{
  "rollouts": [
    {
      "model": "PCSP-full",
      "trajectory_id": "pcsp_full_p241_ep000",
      "persona_id": 241,
      "split": "test",
      "actions": [
        {"step": 1, "action_id": 3},
        {"step": 2, "action_id": 5}
      ]
    }
  ]
}
```

생성 명령:

```bash
conda run -n paper python scripts/generate_persona_identification_survey_ko.py \
  --rollouts results/human_eval/pcsp_zero_shot_rollouts.json \
  --personas data/personas/test_60.json \
  --output_dir data/human_eval
```

설문 응답 CSV는 `participant_id,item_id,response,confidence,response_time_sec` 컬럼을 포함해야 하며, 분석은 다음 명령으로 수행합니다.

```bash
conda run -n paper python src/eval/human_eval.py \
  --csv data/human_eval/prolific_results.csv \
  --answer_key data/human_eval/persona_identification_survey_ko_answer_key.csv \
  --output results/eval/human_eval_summary.json
```

주의: persona metadata에서 만든 synthetic trace는 pilot UI 점검용으로만 사용할 수 있으며, 논문 결과로 보고하면 안 됩니다.
