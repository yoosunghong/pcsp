# Designer-Authored Persona Case Study

Policy: `results/pcsp_v3/full/policy.pt`. Environment: Mini-Inzoi v3, 5 episodes per persona, max_steps=200.
Persona descriptions were authored from the requested Sims 3 trait combinations and Animal Crossing villager personality categories, then encoded with the same Qwen3 last-token-pooling normalization used by training.

| persona_name | top3_actions | nearest_train_persona | cosine_sim |
|---|---|---|---:|
| corporate strategist | focused_work (0.31), planning_work (0.21), eat_slow (0.08) | #95 기업임원 | 0.714 |
| introverted researcher | rest_alone (0.25), read_deep (0.10), socialize_respond (0.08) | #22 SW연구원 | 0.693 |
| outgoing event planner | socialize_initiate (0.15), read_deep (0.08), eat_quick (0.07) | #18 SW연구원 | 0.606 |
| competitive personal trainer | rest_alone (0.21), focused_work (0.13), planning_work (0.09) | #227 운동선수 | 0.752 |
| unmotivated freelancer | rest_alone (0.42), eat_quick (0.07), sleep (0.07) | #74 초등교사 | 0.578 |
| lazy villager | eat_slow (0.14), move_right (0.10), sleep (0.08) | #115 공무원 | 0.614 |
| jock villager | socialize_initiate (0.61), rest_with_others (0.05), eat_slow (0.04) | #237 운동선수 | 0.556 |
| cranky villager | socialize_initiate (0.17), rest_alone (0.13), read_deep (0.06) | #115 공무원 | 0.588 |
| normal villager | focused_work (0.23), socialize_initiate (0.13), eat_slow (0.10) | #58 간호사 | 0.579 |
| peppy villager | socialize_initiate (0.63), eat_slow (0.05), rest_with_others (0.04) | #16 SW연구원 | 0.573 |
| snooty villager | socialize_initiate (0.18), eat_slow (0.09), socialize_respond (0.09) | #35 회계사 | 0.646 |
| smug villager | socialize_initiate (0.28), planning_work (0.07), eat_slow (0.07) | #31 회계사 | 0.612 |
| sisterly villager | socialize_initiate (0.36), eat_slow (0.08), planning_work (0.06) | #213 개인트레이너 | 0.609 |

## Qualitative Commentary

### corporate strategist

This persona was authored from Workaholic + Ambitious + Perfectionist as a 기업 전략가. The expected behavioral signature was focused_work, planning_work, read_deep. Across five v3 rollouts, the top actions were focused_work, planning_work, eat_slow, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: 성실하고 목표 지향적인 기업 전략가입니다. 완성도 높은 계획을 세우는 것을 중요하게 여기며, 쉬는 시간에도 업무 성과와 다음 학습 목표를 점검합니다.
- Bar chart: `results/designer_persona_case_study/action_bars/01_corporate_strategist.png`

### introverted researcher

This persona was authored from Loner + Bookworm + Neurotic as a 내성적인 연구원. The expected behavioral signature was read_deep, rest_alone, planning_work. Across five v3 rollouts, the top actions were rest_alone, read_deep, socialize_respond, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: 조용하고 신중한 내성적인 연구원입니다. 사람 많은 장소보다 혼자 책을 읽고 자료를 정리하는 시간을 선호하며, 불안이 올라오면 익숙한 루틴으로 마음을 가라앉힙니다.
- Bar chart: `results/designer_persona_case_study/action_bars/02_introverted_researcher.png`

### outgoing event planner

This persona was authored from Party Animal + Charismatic + Friendly as a 이벤트 플래너. The expected behavioral signature was socialize_initiate, socialize_respond, rest_with_others. Across five v3 rollouts, the top actions were socialize_initiate, read_deep, eat_quick, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: 사교적이고 붙임성 좋은 이벤트 플래너입니다. 사람들을 한자리에 모으고 분위기를 띄우는 데 에너지를 얻으며, 하루 일과도 대화와 공동 휴식 중심으로 흘러갑니다.
- Bar chart: `results/designer_persona_case_study/action_bars/03_outgoing_event_planner.png`

### competitive personal trainer

This persona was authored from Athletic + Brave + Disciplined as a 개인 트레이너. The expected behavioral signature was exercise_intense, exercise_light, focused_work. Across five v3 rollouts, the top actions were rest_alone, focused_work, planning_work, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: 용감하고 절제력이 강한 개인 트레이너입니다. 경쟁적인 운동 목표를 세우고 꾸준히 몸을 단련하며, 어려운 상황에서도 먼저 행동하는 편입니다.
- Bar chart: `results/designer_persona_case_study/action_bars/04_competitive_personal_trainer.png`

### unmotivated freelancer

This persona was authored from Couch Potato + Slob + Lazy as a 프리랜서. The expected behavioral signature was eat_quick, sleep, rest_alone. Across five v3 rollouts, the top actions were rest_alone, eat_quick, sleep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: 느긋하고 의욕이 낮은 프리랜서입니다. 일을 미루고 소파에서 쉬거나 간단히 먹는 습관이 있으며, 청소나 운동처럼 에너지가 많이 드는 일은 자주 피합니다.
- Bar chart: `results/designer_persona_case_study/action_bars/05_unmotivated_freelancer.png`

### lazy villager

This persona was authored from Lazy personality as a 느긋한 마을 주민. The expected behavioral signature was eat_slow, sleep, rest_alone. Across five v3 rollouts, the top actions were eat_slow, move_right, sleep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: 음식과 잠을 좋아하는 느긋한 마을 주민입니다. 서두르기보다 천천히 먹고 쉬는 일상을 즐기며, 친근하지만 큰 계획에는 별로 매달리지 않습니다.
- Bar chart: `results/designer_persona_case_study/action_bars/06_lazy_villager.png`

### jock villager

This persona was authored from Jock personality as a 운동광 마을 주민. The expected behavioral signature was exercise_intense, exercise_light, explore. Across five v3 rollouts, the top actions were socialize_initiate, rest_with_others, eat_slow, giving weak alignment. This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: 운동에 집착하는 활기찬 마을 주민입니다. 하루의 대부분을 체력 단련과 활동적인 놀이로 채우고, 대화에서도 더 강해지는 방법을 자주 이야기합니다.
- Bar chart: `results/designer_persona_case_study/action_bars/07_jock_villager.png`

### cranky villager

This persona was authored from Cranky personality as a 무뚝뚝한 마을 주민. The expected behavioral signature was rest_alone, read_deep, clean. Across five v3 rollouts, the top actions were socialize_initiate, rest_alone, read_deep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: 고집 있고 옛 방식을 좋아하는 무뚝뚝한 마을 주민입니다. 처음에는 까칠하게 굴지만 익숙한 사람에게는 조용히 챙겨 주며, 유행보다 혼자 쉬는 시간을 더 편하게 여깁니다.
- Bar chart: `results/designer_persona_case_study/action_bars/08_cranky_villager.png`

### normal villager

This persona was authored from Normal personality as a 다정한 마을 주민. The expected behavioral signature was clean, socialize_respond, rest_with_others. Across five v3 rollouts, the top actions were focused_work, socialize_initiate, eat_slow, giving weak alignment. This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: 위생과 정돈을 중시하는 다정하고 보살피는 마을 주민입니다. 차분한 루틴 속에서 청소와 자기관리를 챙기며, 주변 사람이 편안하게 지내도록 조용히 도와줍니다.
- Bar chart: `results/designer_persona_case_study/action_bars/09_normal_villager.png`

### peppy villager

This persona was authored from Peppy personality as a 팝스타 지망생. The expected behavioral signature was socialize_initiate, explore, rest_with_others. Across five v3 rollouts, the top actions were socialize_initiate, eat_slow, rest_with_others, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: 팝스타를 꿈꾸는 에너지 넘치는 마을 주민입니다. 새로운 사람에게 먼저 말을 걸고 활동적인 놀이를 즐기며, 하루를 공연 연습처럼 밝고 빠르게 움직입니다.
- Bar chart: `results/designer_persona_case_study/action_bars/10_peppy_villager.png`

### snooty villager

This persona was authored from Snooty personality as a 패션 애호가. The expected behavioral signature was clean, planning_work, socialize_initiate. Across five v3 rollouts, the top actions were socialize_initiate, eat_slow, socialize_respond, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: 패션에 집착하고 자기 기준이 뚜렷한 마을 주민입니다. 세련된 모습을 유지하는 데 신경을 쓰며, 남들과 어울릴 때도 자신감 있고 약간 거리를 둔 태도를 보입니다.
- Bar chart: `results/designer_persona_case_study/action_bars/11_snooty_villager.png`

### smug villager

This persona was authored from Smug personality as a 신사적인 마을 주민. The expected behavioral signature was socialize_initiate, socialize_respond, planning_work. Across five v3 rollouts, the top actions were socialize_initiate, planning_work, eat_slow, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: 신사적이지만 스스로에게 꽤 만족하는 마을 주민입니다. 매너 있는 대화를 즐기고 자기 취향을 자주 드러내며, 일과 휴식 모두를 멋지게 보이도록 조율하려 합니다.
- Bar chart: `results/designer_persona_case_study/action_bars/12_smug_villager.png`

### sisterly villager

This persona was authored from Sisterly / Uchi personality as a 보호적인 마을 주민. The expected behavioral signature was socialize_respond, rest_with_others, exercise_intense. Across five v3 rollouts, the top actions were socialize_initiate, eat_slow, planning_work, giving weak alignment. This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: 직설적이고 씩씩하며 주변 사람을 보호하려는 마을 주민입니다. 말투는 거칠 수 있지만 도움이 필요한 사람에게 먼저 다가가고, 활동적인 일과 공동 휴식을 모두 중요하게 여깁니다.
- Bar chart: `results/designer_persona_case_study/action_bars/13_sisterly_villager.png`
