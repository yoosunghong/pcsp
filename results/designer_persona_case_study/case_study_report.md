# Designer-Authored Persona Case Study

Policy: `results/pcsp_v3/full/policy.pt`. Environment: Mini-Inzoi v3, 5 episodes per persona, max_steps=200.
Persona descriptions were authored from five sources: The Sims 3 trait combinations, Animal Crossing villager personality categories, Stardew Valley NPC archetypes, Persona-series confidants, and original designer briefs. All were encoded with the same Qwen3 last-token-pooling normalization used by training.

## Outcome summary by source

| source | n | success | partial | failure | top failure mode |
|---|---:|---:|---:|---:|---|
| The Sims 3 | 10 | 4 | 5 | 1 | F1_ontology_gap |
| Animal Crossing | 12 | 4 | 5 | 3 | F5_residual |
| Stardew Valley | 10 | 5 | 4 | 1 | F1_ontology_gap |
| Persona Series | 6 | 4 | 2 | 0 | — |
| Original Designer Brief | 12 | 5 | 5 | 2 | F4_trait_collision |
| **total** | **50** | **22** | **21** | **7** | F1_ontology_gap |

## Per-persona results

| persona_name | source | top3_actions | outcome | failure_mode | nearest_train_persona | cosine_sim |
|---|---|---|---|---|---|---:|
| corporate strategist | The Sims 3 | planning_work (0.26), read_deep (0.10), focused_work (0.09) | success | — | #96 기업임원 | 0.665 |
| introverted researcher | The Sims 3 | rest_alone (0.34), read_deep (0.10), planning_work (0.09) | success | — | #186 대학원생 | 0.617 |
| outgoing event planner | The Sims 3 | socialize_initiate (0.29), planning_work (0.09), eat_slow (0.07) | partial | — | #213 개인트레이너 | 0.667 |
| competitive personal trainer | The Sims 3 | socialize_initiate (0.46), focused_work (0.09), exercise_intense (0.09) | success | — | #227 운동선수 | 0.663 |
| unmotivated freelancer | The Sims 3 | rest_alone (0.29), socialize_initiate (0.22), rest_with_others (0.10) | partial | — | #31 회계사 | 0.618 |
| lazy villager | Animal Crossing | rest_alone (0.39), socialize_initiate (0.11), socialize_respond (0.07) | partial | — | #220 개인트레이너 | 0.651 |
| jock villager | Animal Crossing | socialize_initiate (0.60), eat_slow (0.05), rest_with_others (0.04) | failure | F5_residual | #226 운동선수 | 0.550 |
| cranky villager | Animal Crossing | socialize_initiate (0.14), sleep (0.08), eat_slow (0.08) | failure | F2_style_reward_conflict | #35 회계사 | 0.544 |
| normal villager | Animal Crossing | planning_work (0.16), focused_work (0.09), eat_slow (0.09) | failure | F1_ontology_gap | #220 개인트레이너 | 0.650 |
| peppy villager | Animal Crossing | socialize_initiate (0.72), eat_slow (0.04), rest_with_others (0.03) | success | — | #31 회계사 | 0.574 |
| snooty villager | Animal Crossing | focused_work (0.26), socialize_initiate (0.10), eat_slow (0.09) | partial | — | #125 그래픽디자이너 | 0.570 |
| smug villager | Animal Crossing | socialize_initiate (0.18), planning_work (0.15), read_deep (0.12) | success | — | #31 회계사 | 0.558 |
| sisterly villager | Animal Crossing | socialize_initiate (0.41), eat_slow (0.06), exercise_intense (0.06) | partial | — | #78 영업사원 | 0.594 |
| bookworm librarian | The Sims 3 | planning_work (0.18), read_deep (0.13), sleep (0.09) | success | — | #186 대학원생 | 0.512 |
| charismatic sales manager | The Sims 3 | socialize_initiate (0.58), read_deep (0.07), eat_slow (0.05) | partial | — | #31 회계사 | 0.562 |
| family-oriented caretaker | The Sims 3 | planning_work (0.20), socialize_initiate (0.14), eat_slow (0.08) | failure | F1_ontology_gap | #115 공무원 | 0.596 |
| bohemian illustrator | The Sims 3 | socialize_initiate (0.22), planning_work (0.09), read_deep (0.09) | partial | — | #181 대학원생 | 0.570 |
| hot-headed adventurer | The Sims 3 | socialize_initiate (0.82), rest_with_others (0.03), sleep (0.02) | partial | — | #229 운동선수 | 0.648 |
| big sister bar manager | Animal Crossing | focused_work (0.33), rest_with_others (0.08), socialize_respond (0.07) | success | — | #93 기업임원 | 0.508 |
| sleepy night guard | Animal Crossing | rest_alone (0.56), socialize_respond (0.07), sleep (0.06) | success | — | #31 회계사 | 0.494 |
| energetic schoolkid | Animal Crossing | socialize_initiate (0.93), rest_with_others (0.01), focused_work (0.01) | partial | — | #181 대학원생 | 0.537 |
| anxious cafe worker | Animal Crossing | rest_alone (0.27), read_deep (0.09), planning_work (0.07) | partial | — | #36 회계사 | 0.555 |
| conservative mayor | Stardew Valley | socialize_initiate (0.30), focused_work (0.19), eat_slow (0.08) | partial | — | #217 개인트레이너 | 0.600 |
| shopkeeper | Stardew Valley | socialize_initiate (0.21), rest_alone (0.10), planning_work (0.08) | success | — | #81 영업사원 | 0.524 |
| skilled carpenter | Stardew Valley | planning_work (0.18), focused_work (0.15), eat_slow (0.10) | success | — | #130 그래픽디자이너 | 0.535 |
| environmental scientist | Stardew Valley | socialize_initiate (0.63), read_deep (0.06), focused_work (0.06) | success | — | #186 대학원생 | 0.548 |
| reclusive freelance coder | Stardew Valley | rest_alone (0.51), read_deep (0.07), planning_work (0.05) | success | — | #126 그래픽디자이너 | 0.547 |
| adventurous student | Stardew Valley | socialize_initiate (0.69), read_deep (0.04), sleep (0.04) | partial | — | #31 회계사 | 0.531 |
| caring tutor | Stardew Valley | planning_work (0.20), read_deep (0.10), socialize_respond (0.08) | success | — | #115 공무원 | 0.556 |
| off-grid hermit | Stardew Valley | rest_alone (0.70), read_deep (0.04), sleep (0.03) | partial | — | #142 작가 | 0.484 |
| recovering retail worker | Stardew Valley | rest_alone (0.20), socialize_initiate (0.12), rest_with_others (0.09) | partial | — | #119 공무원 | 0.518 |
| animal clinic worker | Stardew Valley | socialize_initiate (0.51), focused_work (0.12), eat_slow (0.06) | failure | F1_ontology_gap | #55 간호사 | 0.547 |
| gruff cafe owner | Persona Series | rest_alone (0.29), eat_slow (0.09), sleep (0.06) | partial | — | #97 기업임원 | 0.570 |
| eccentric art student | Persona Series | socialize_initiate (0.80), read_deep (0.03), planning_work (0.03) | success | — | #181 대학원생 | 0.525 |
| perfectionist student leader | Persona Series | focused_work (0.47), eat_slow (0.09), planning_work (0.07) | success | — | #186 대학원생 | 0.603 |
| hikikomori hacker | Persona Series | focused_work (0.14), socialize_respond (0.10), read_deep (0.08) | success | — | #31 회계사 | 0.501 |
| rising model | Persona Series | socialize_initiate (0.24), planning_work (0.12), eat_slow (0.10) | partial | — | #31 회계사 | 0.639 |
| impulsive sprinter | Persona Series | socialize_initiate (0.35), rest_alone (0.22), rest_with_others (0.09) | success | — | #226 운동선수 | 0.569 |
| burned-out doctor | Original Designer Brief | focused_work (0.25), planning_work (0.13), sleep (0.09) | success | — | #54 간호사 | 0.531 |
| cynical journalist | Original Designer Brief | focused_work (0.10), read_deep (0.10), planning_work (0.10) | success | — | #186 대학원생 | 0.495 |
| optimistic single parent | Original Designer Brief | planning_work (0.16), socialize_initiate (0.13), eat_slow (0.09) | partial | — | #115 공무원 | 0.553 |
| introverted gourmet chef | Original Designer Brief | rest_alone (0.48), planning_work (0.10), read_deep (0.06) | partial | — | #126 그래픽디자이너 | 0.569 |
| anxious composer | Original Designer Brief | socialize_initiate (0.14), focused_work (0.12), read_deep (0.08) | success | — | #199 번역가 | 0.455 |
| stoic engineer | Original Designer Brief | rest_alone (0.41), focused_work (0.12), socialize_respond (0.10) | partial | — | #7 마케터 | 0.621 |
| empathic counselor | Original Designer Brief | rest_alone (0.53), socialize_respond (0.06), planning_work (0.05) | success | — | #115 공무원 | 0.618 |
| eccentric retired professor | Original Designer Brief | rest_alone (0.24), socialize_initiate (0.11), read_deep (0.09) | partial | — | #31 회계사 | 0.462 |
| sleep-deprived startup founder | Original Designer Brief | socialize_initiate (0.31), read_deep (0.09), read_casual (0.08) | failure | F4_trait_collision | #158 창업자 | 0.572 |
| routine-driven retiree | Original Designer Brief | socialize_initiate (0.15), eat_slow (0.09), exercise_intense (0.08) | partial | — | #73 초등교사 | 0.641 |
| quiet family caretaker | Original Designer Brief | rest_alone (0.24), socialize_respond (0.14), focused_work (0.07) | success | — | #55 간호사 | 0.540 |
| restless rideshare driver | Original Designer Brief | socialize_initiate (0.97), sleep (0.01), rest_with_others (0.01) | failure | F2_style_reward_conflict | #31 회계사 | 0.574 |

## Qualitative Commentary

### corporate strategist

This persona was authored from Workaholic + Ambitious + Perfectionist as a 기업 전략가. The expected behavioral signature was focused_work, planning_work, read_deep. Across five v3 rollouts, the top actions were planning_work, read_deep, focused_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A disciplined, goal-oriented corporate strategist. He cares deeply about polished plans, and even during breaks reviews his recent work and the next learning targets he has set for himself.
- Bar chart: `results/designer_persona_case_study/action_bars/01_corporate_strategist.png`

### introverted researcher

This persona was authored from Loner + Bookworm + Neurotic as a 내성적인 연구원. The expected behavioral signature was read_deep, rest_alone, planning_work. Across five v3 rollouts, the top actions were rest_alone, read_deep, planning_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A quiet, careful introverted researcher. She prefers reading and organizing material alone over crowded places, and when anxiety creeps in she settles herself by retreating into familiar routines.
- Bar chart: `results/designer_persona_case_study/action_bars/02_introverted_researcher.png`

### outgoing event planner

This persona was authored from Party Animal + Charismatic + Friendly as a 이벤트 플래너. The expected behavioral signature was socialize_initiate, socialize_respond, rest_with_others. Across five v3 rollouts, the top actions were socialize_initiate, planning_work, eat_slow, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A sociable, warm event planner. She gets her energy from gathering people together and lifting the mood, and her day naturally flows around conversation and shared downtime.
- Bar chart: `results/designer_persona_case_study/action_bars/03_outgoing_event_planner.png`

### competitive personal trainer

This persona was authored from Athletic + Brave + Disciplined as a 개인 트레이너. The expected behavioral signature was exercise_intense, exercise_light, focused_work. Across five v3 rollouts, the top actions were socialize_initiate, focused_work, exercise_intense, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A brave, highly disciplined personal trainer. He sets competitive training goals, keeps a steady conditioning routine, and tends to act first when things get tough.
- Bar chart: `results/designer_persona_case_study/action_bars/04_competitive_personal_trainer.png`

### unmotivated freelancer

This persona was authored from Couch Potato + Slob + Lazy as a 프리랜서. The expected behavioral signature was eat_quick, sleep, rest_alone. Across five v3 rollouts, the top actions were rest_alone, socialize_initiate, rest_with_others, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: An easygoing, low-motivation freelancer. He puts off work to lounge on the couch or grab quick meals, and avoids energy-intensive chores like cleaning or exercise.
- Bar chart: `results/designer_persona_case_study/action_bars/05_unmotivated_freelancer.png`

### lazy villager

This persona was authored from Lazy personality as a 느긋한 마을 주민. The expected behavioral signature was eat_slow, sleep, rest_alone. Across five v3 rollouts, the top actions were rest_alone, socialize_initiate, socialize_respond, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: An easygoing villager who loves food and sleep. He prefers a slow-eating, rest-heavy daily rhythm over rushing around, and is friendly without getting attached to big plans.
- Bar chart: `results/designer_persona_case_study/action_bars/06_lazy_villager.png`

### jock villager

This persona was authored from Jock personality as a 운동광 마을 주민. The expected behavioral signature was exercise_intense, exercise_light, explore. Across five v3 rollouts, the top actions were socialize_initiate, eat_slow, rest_with_others, giving weak alignment (F5_residual). This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: An energetic villager who obsesses over fitness. He fills most of the day with conditioning and active games, and even his conversations gravitate toward how to get stronger.
- Bar chart: `results/designer_persona_case_study/action_bars/07_jock_villager.png`

### cranky villager

This persona was authored from Cranky personality as a 무뚝뚝한 마을 주민. The expected behavioral signature was rest_alone, read_deep, clean. Across five v3 rollouts, the top actions were socialize_initiate, sleep, eat_slow, giving weak alignment (F2_style_reward_conflict). This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: A stubborn, old-fashioned villager with a gruff exterior. He comes off prickly at first but quietly looks out for the people he knows, and is more at ease in solitary downtime than in anything fashionable.
- Bar chart: `results/designer_persona_case_study/action_bars/08_cranky_villager.png`

### normal villager

This persona was authored from Normal personality as a 다정한 마을 주민. The expected behavioral signature was clean, socialize_respond, rest_with_others. Across five v3 rollouts, the top actions were planning_work, focused_work, eat_slow, giving weak alignment (F1_ontology_gap). This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: A gentle, attentive villager who cares about hygiene and tidiness. She keeps a calm routine of cleaning and self-care, and quietly helps the people around her feel at ease.
- Bar chart: `results/designer_persona_case_study/action_bars/09_normal_villager.png`

### peppy villager

This persona was authored from Peppy personality as a 팝스타 지망생. The expected behavioral signature was socialize_initiate, explore, rest_with_others. Across five v3 rollouts, the top actions were socialize_initiate, eat_slow, rest_with_others, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: An upbeat villager who dreams of becoming a pop star. She talks to strangers first, enjoys active play, and moves through the day as if it were a rehearsal — bright and fast-paced.
- Bar chart: `results/designer_persona_case_study/action_bars/10_peppy_villager.png`

### snooty villager

This persona was authored from Snooty personality as a 패션 애호가. The expected behavioral signature was clean, planning_work, socialize_initiate. Across five v3 rollouts, the top actions were focused_work, socialize_initiate, eat_slow, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A villager obsessed with fashion who holds firm to her own standards. She works at staying polished, and even in company she carries herself with a confident, slightly distant air.
- Bar chart: `results/designer_persona_case_study/action_bars/11_snooty_villager.png`

### smug villager

This persona was authored from Smug personality as a 신사적인 마을 주민. The expected behavioral signature was socialize_initiate, socialize_respond, planning_work. Across five v3 rollouts, the top actions were socialize_initiate, planning_work, read_deep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A gentlemanly villager who is rather pleased with himself. He enjoys mannered conversation, shows off his tastes often, and tries to arrange both work and rest so they look impressive.
- Bar chart: `results/designer_persona_case_study/action_bars/12_smug_villager.png`

### sisterly villager

This persona was authored from Sisterly / Uchi personality as a 보호적인 마을 주민. The expected behavioral signature was socialize_respond, rest_with_others, exercise_intense. Across five v3 rollouts, the top actions were socialize_initiate, eat_slow, exercise_intense, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A blunt, spirited villager who instinctively protects the people around her. Her tone can be rough, but she steps in first when someone needs help, and values both active work and shared downtime.
- Bar chart: `results/designer_persona_case_study/action_bars/13_sisterly_villager.png`

### bookworm librarian

This persona was authored from Genius + Bookworm + Coward as a 내성적인 도서관 사서. The expected behavioral signature was read_deep, planning_work, rest_alone. Across five v3 rollouts, the top actions were planning_work, read_deep, sleep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A librarian devoted to books and research material. Stepping in front of crowds feels heavy, but during solitary deep-study hours she focuses harder than anyone.
- Bar chart: `results/designer_persona_case_study/action_bars/14_bookworm_librarian.png`

### charismatic sales manager

This persona was authored from Charismatic + Schmoozer + Ambitious as a 사교적 영업 매니저. The expected behavioral signature was socialize_initiate, planning_work, socialize_respond. Across five v3 rollouts, the top actions were socialize_initiate, read_deep, eat_slow, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A sales manager skilled at persuading people and steering a room. He enjoys meeting new contacts and is constantly planning and moving in pursuit of the next, bigger deal.
- Bar chart: `results/designer_persona_case_study/action_bars/15_charismatic_sales_manager.png`

### family-oriented caretaker

This persona was authored from Family-Oriented + Friendly + Good as a 가정적인 아이돌봄 봉사자. The expected behavioral signature was socialize_respond, rest_with_others, clean. Across five v3 rollouts, the top actions were planning_work, socialize_initiate, eat_slow, giving weak alignment (F1_ontology_gap). This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: A warm caretaker who finds meaning in looking after children and family. She enjoys offering kind words and simply spending time alongside the people she cares about.
- Bar chart: `results/designer_persona_case_study/action_bars/16_family-oriented_caretaker.png`

### bohemian illustrator

This persona was authored from Artistic + Bohemian + Eccentric as a 자유로운 일러스트레이터. The expected behavioral signature was explore, read_casual, socialize_initiate. Across five v3 rollouts, the top actions were socialize_initiate, planning_work, read_deep, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A free-spirited, curious illustrator. She draws when inspiration strikes rather than on a fixed schedule, and loves wandering through cafes and unfamiliar neighborhoods for new material.
- Bar chart: `results/designer_persona_case_study/action_bars/17_bohemian_illustrator.png`

### hot-headed adventurer

This persona was authored from Hot-Headed + Daredevil + Brave as a 충동적인 모험가. The expected behavioral signature was explore, exercise_intense, socialize_initiate. Across five v3 rollouts, the top actions were socialize_initiate, rest_with_others, sleep, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: An impulsive adventurer who throws himself into risky situations first. He grows restless without new experiences, and his quick temper comes paired with a matching lack of fear.
- Bar chart: `results/designer_persona_case_study/action_bars/18_hot-headed_adventurer.png`

### big sister bar manager

This persona was authored from Big Sister (uchi variant) as a 단단한 술집 매니저. The expected behavioral signature was socialize_initiate, rest_with_others, socialize_respond. Across five v3 rollouts, the top actions were focused_work, rest_with_others, socialize_respond, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A solid bar manager who looks after both customers and staff. There is a warmth beneath her rough way of talking, and she approaches anyone who looks like they are struggling without waiting to be asked.
- Bar chart: `results/designer_persona_case_study/action_bars/19_big_sister_bar_manager.png`

### sleepy night guard

This persona was authored from Sleepy + Lazy composite as a 졸린 야간 경비원. The expected behavioral signature was nap, rest_alone, sleep. Across five v3 rollouts, the top actions were rest_alone, socialize_respond, sleep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A perpetually drowsy night guard. During quiet hours he leans back in his chair to rest or takes a short nap, and is happy with a quiet routine as long as nothing serious happens.
- Bar chart: `results/designer_persona_case_study/action_bars/20_sleepy_night_guard.png`

### energetic schoolkid

This persona was authored from Energetic Kid (peppy variant) as a 호기심 많은 초등학생. The expected behavioral signature was explore, exercise_light, socialize_initiate. Across five v3 rollouts, the top actions were socialize_initiate, rest_with_others, focused_work, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A curious elementary schooler. She cannot sit still, runs around the playground with her friends, and dives straight into any new game she discovers.
- Bar chart: `results/designer_persona_case_study/action_bars/21_energetic_schoolkid.png`

### anxious cafe worker

This persona was authored from Anxious (designer composite) as a 신경 많은 카페 알바생. The expected behavioral signature was socialize_respond, read_casual, rest_alone. Across five v3 rollouts, the top actions were rest_alone, read_deep, planning_work, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A cafe part-timer who frets over small mistakes. She wants to handle customers well but her mind often races, and during quiet stretches she opens a book by herself.
- Bar chart: `results/designer_persona_case_study/action_bars/22_anxious_cafe_worker.png`

### conservative mayor

This persona was authored from Lewis — conservative mayor as a 보수적 시장. The expected behavioral signature was focused_work, planning_work, clean. Across five v3 rollouts, the top actions were socialize_initiate, focused_work, eat_slow, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A conservative mayor who guards the town's traditions. He prefers to move on a fixed schedule and prioritizes stable administration over sweeping change.
- Bar chart: `results/designer_persona_case_study/action_bars/23_conservative_mayor.png`

### shopkeeper

This persona was authored from Pierre — small shop owner as a 자영업 가게 주인. The expected behavioral signature was socialize_initiate, planning_work, socialize_respond. Across five v3 rollouts, the top actions were socialize_initiate, rest_alone, planning_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: An energetic, sharp-minded small-shop owner. He chats easily with customers while quietly running sales and inventory numbers in his head.
- Bar chart: `results/designer_persona_case_study/action_bars/24_shopkeeper.png`

### skilled carpenter

This persona was authored from Robin — veteran carpenter as a 손재주 좋은 목수. The expected behavioral signature was focused_work, planning_work, rest_with_others. Across five v3 rollouts, the top actions were planning_work, focused_work, eat_slow, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A veteran carpenter with excellent hands. She calmly reviews drawings and plans the next job, and works hard to balance her craft and her family.
- Bar chart: `results/designer_persona_case_study/action_bars/25_skilled_carpenter.png`

### environmental scientist

This persona was authored from Demetrius — research-driven scientist as a 환경 과학자. The expected behavioral signature was read_deep, focused_work, planning_work. Across five v3 rollouts, the top actions were socialize_initiate, read_deep, focused_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: An environmental scientist who keeps revisiting data and hypotheses. New data excites him, and he does not stop studying and analyzing until a clear answer emerges.
- Bar chart: `results/designer_persona_case_study/action_bars/26_environmental_scientist.png`

### reclusive freelance coder

This persona was authored from Sebastian — reclusive coder as a 은둔형 프리랜서 개발자. The expected behavioral signature was focused_work, rest_alone, read_deep. Across five v3 rollouts, the top actions were rest_alone, read_deep, planning_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A reclusive freelance developer who keeps code and music closer than people. He works quietly in his room during the day and most dislikes anyone intruding on his time.
- Bar chart: `results/designer_persona_case_study/action_bars/27_reclusive_freelance_coder.png`

### adventurous student

This persona was authored from Abigail — adventurous goth student as a 모험가 기질 학생. The expected behavioral signature was explore, socialize_initiate, read_casual. Across five v3 rollouts, the top actions were socialize_initiate, read_deep, sleep, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A student drawn to the unfamiliar. She prefers imagining herself exploring dungeons, ruins, and mysteries over the regular day-to-day, and finds sitting still suffocating.
- Bar chart: `results/designer_persona_case_study/action_bars/28_adventurous_student.png`

### caring tutor

This persona was authored from Penny — caring small-town tutor as a 동네 학원 교사. The expected behavioral signature was read_deep, socialize_respond, clean. Across five v3 rollouts, the top actions were planning_work, read_deep, socialize_respond, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A gentle after-school tutor who reads books to children. She likes a calm routine and values doing a little bit each day to help the kids grow.
- Bar chart: `results/designer_persona_case_study/action_bars/29_caring_tutor.png`

### off-grid hermit

This persona was authored from Linus — off-grid hermit as a 자급자족 은둔자. The expected behavioral signature was rest_alone, explore, read_casual. Across five v3 rollouts, the top actions were rest_alone, read_deep, sleep, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A hermit living self-sufficiently at the foot of a mountain. He values nature and solitary time over the bustle of society, and lives frugally, working only as much as he needs to.
- Bar chart: `results/designer_persona_case_study/action_bars/30_off-grid_hermit.png`

### recovering retail worker

This persona was authored from Shane — recovering depression arc as a 회복기 마트 직원. The expected behavioral signature was rest_alone, focused_work, socialize_respond. Across five v3 rollouts, the top actions were rest_alone, socialize_initiate, rest_with_others, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A grocery worker easing back into daily life with a heavy heart. Crowded settings still feel like a burden, but he is slowly recovering through brief stretches with coworkers and quietly doing his own work.
- Bar chart: `results/designer_persona_case_study/action_bars/31_recovering_retail_worker.png`

### animal clinic worker

This persona was authored from Marnie — caring rancher as a 동물병원 직원. The expected behavioral signature was socialize_respond, rest_with_others, clean. Across five v3 rollouts, the top actions were socialize_initiate, focused_work, eat_slow, giving weak alignment (F1_ontology_gap). This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: An animal clinic worker who looks after both animals and people kindly. She moves through her day with a calm warmth around coworkers and finds meaning in small everyday acts of care.
- Bar chart: `results/designer_persona_case_study/action_bars/32_animal_clinic_worker.png`

### gruff cafe owner

This persona was authored from Sojiro — gruff but caring guardian as a 무뚝뚝한 카페 사장. The expected behavioral signature was eat_slow, focused_work, socialize_respond. Across five v3 rollouts, the top actions were rest_alone, eat_slow, sleep, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A gruff but warm-hearted cafe owner. He keeps a polite distance from customers while quietly looking after the people close to him, and prefers running the shop at his own steady pace.
- Bar chart: `results/designer_persona_case_study/action_bars/33_gruff_cafe_owner.png`

### eccentric art student

This persona was authored from Yusuke — eccentric art student as a 미술학도. The expected behavioral signature was read_deep, explore, planning_work. Across five v3 rollouts, the top actions were socialize_initiate, read_deep, planning_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: An eccentric art student who lives by inspiration. He often skips meals or works until dawn on a piece, and constantly searches even mundane scenes for new motifs.
- Bar chart: `results/designer_persona_case_study/action_bars/34_eccentric_art_student.png`

### perfectionist student leader

This persona was authored from Makoto — perfectionist student council president as a 모범생 학생회장. The expected behavioral signature was read_deep, planning_work, focused_work. Across five v3 rollouts, the top actions were focused_work, eat_slow, planning_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A perfectionist student council president with a strong sense of responsibility. She juggles exam prep and council duties without slipping, and disciplines herself to stay steady when others lean on her.
- Bar chart: `results/designer_persona_case_study/action_bars/35_perfectionist_student_leader.png`

### hikikomori hacker

This persona was authored from Futaba — hikikomori hacker as a 히키코모리 해커. The expected behavioral signature was focused_work, rest_alone, read_deep. Across five v3 rollouts, the top actions were focused_work, socialize_respond, read_deep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A hikikomori hacker who rarely leaves her room. She is fluent with the world behind a screen but finds face-to-face contact difficult, and feels safest within the familiar routine of her own space.
- Bar chart: `results/designer_persona_case_study/action_bars/36_hikikomori_hacker.png`

### rising model

This persona was authored from Ann — image-conscious rising model as a 신인 모델. The expected behavioral signature was exercise_light, socialize_initiate, clean. Across five v3 rollouts, the top actions were socialize_initiate, planning_work, eat_slow, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A rising model who pays close attention to her appearance and reputation. She is outgoing and sociable but disciplined about self-care, and shows a surprisingly earnest side around close friends.
- Bar chart: `results/designer_persona_case_study/action_bars/37_rising_model.png`

### impulsive sprinter

This persona was authored from Ryuji — impulsive sprinter with injury arc as a 단거리 선수. The expected behavioral signature was exercise_intense, socialize_initiate, rest_with_others. Across five v3 rollouts, the top actions were socialize_initiate, rest_alone, rest_with_others, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: An impulsive, fiercely loyal short-distance sprinter. He throws himself into training and is loud and animated around his friends, but quietly carries the frustration of a leg injury that interrupted his career.
- Bar chart: `results/designer_persona_case_study/action_bars/38_impulsive_sprinter.png`

### burned-out doctor

This persona was authored from High C + High N + Low E as a 번아웃 의사. The expected behavioral signature was sleep, rest_alone, focused_work. Across five v3 rollouts, the top actions were focused_work, planning_work, sleep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A burned-out doctor who has been working overnight shifts for years. She stays composed in front of patients but, once the day ends, desperately needs time alone because of deep fatigue and low mood.
- Bar chart: `results/designer_persona_case_study/action_bars/39_burned-out_doctor.png`

### cynical journalist

This persona was authored from High O + High N + Low A as a 냉소적인 기자. The expected behavioral signature was read_deep, planning_work, focused_work. Across five v3 rollouts, the top actions were focused_work, read_deep, planning_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A cynical journalist skilled at digging out facts and contradictions. He does not take people at their word, verifies sources to the end, and cuts into his sleep to keep investigating when a case is interesting.
- Bar chart: `results/designer_persona_case_study/action_bars/40_cynical_journalist.png`

### optimistic single parent

This persona was authored from High E + High A + Low N as a 낙천적인 한부모. The expected behavioral signature was socialize_respond, rest_with_others, eat_slow. Across five v3 rollouts, the top actions were planning_work, socialize_initiate, eat_slow, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: An optimistic single parent who keeps her humor through hard situations. She draws energy from time with her child and brief conversations with neighbors, and shapes her day around her family.
- Bar chart: `results/designer_persona_case_study/action_bars/41_optimistic_single_parent.png`

### introverted gourmet chef

This persona was authored from Low E + High C + High O as a 내성적 셰프. The expected behavioral signature was eat_slow, focused_work, rest_alone. Across five v3 rollouts, the top actions were rest_alone, planning_work, read_deep, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A quiet but uncompromising chef who is introverted about everything except food. He explores new ingredients, savors meals slowly, and prefers spending most of his time alone refining the menu.
- Bar chart: `results/designer_persona_case_study/action_bars/42_introverted_gourmet_chef.png`

### anxious composer

This persona was authored from High N + High C + High O as a 신경증적 작곡가. The expected behavioral signature was focused_work, read_deep, rest_alone. Across five v3 rollouts, the top actions were socialize_initiate, focused_work, read_deep, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: An anxious composer fixated on polish. He rewrites every bar again and again, and when his condition wavers he cuts sleep or replays the same piece on loop to soothe the anxiety.
- Bar chart: `results/designer_persona_case_study/action_bars/43_anxious_composer.png`

### stoic engineer

This persona was authored from Low E + Low N + High C as a 과묵한 엔지니어. The expected behavioral signature was focused_work, planning_work, read_deep. Across five v3 rollouts, the top actions were rest_alone, focused_work, socialize_respond, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A stoic engineer who keeps his emotions to himself. He prefers fixed schedules and clear rules, and when problems arise he works through them one calm step at a time.
- Bar chart: `results/designer_persona_case_study/action_bars/44_stoic_engineer.png`

### empathic counselor

This persona was authored from High A + High O + Mid N as a 공감 상담사. The expected behavioral signature was socialize_respond, rest_alone, rest_with_others. Across five v3 rollouts, the top actions were rest_alone, socialize_respond, planning_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: An empathic counselor who listens deeply. She is skilled at slow conversation that helps the other person settle, and deliberately carves out quiet downtime to look after herself.
- Bar chart: `results/designer_persona_case_study/action_bars/45_empathic_counselor.png`

### eccentric retired professor

This persona was authored from High O + Mid N + High C as a 별난 은퇴 교수. The expected behavioral signature was read_deep, eat_slow, socialize_respond. Across five v3 rollouts, the top actions were rest_alone, socialize_initiate, read_deep, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: An eccentric retired professor who cannot put down books and papers even in retirement. He reads articles until early morning, savors a late lunch slowly, and occasionally enjoys long conversations with former students.
- Bar chart: `results/designer_persona_case_study/action_bars/46_eccentric_retired_professor.png`

### sleep-deprived startup founder

This persona was authored from High E + High C + High O as a 잠이 부족한 창업가. The expected behavioral signature was focused_work, planning_work, eat_quick. Across five v3 rollouts, the top actions were socialize_initiate, read_deep, read_casual, giving weak alignment (F4_trait_collision). This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: A startup founder polishing the product on too little sleep. He moves quickly between meetings and work, pulls up materials whenever an idea strikes even before dawn, and tends to grab meals quickly without much thought.
- Bar chart: `results/designer_persona_case_study/action_bars/47_sleep-deprived_startup_founder.png`

### routine-driven retiree

This persona was authored from Mid E + Low N + High C + Low O as a 규칙적인 은퇴자. The expected behavioral signature was clean, exercise_light, eat_slow. Across five v3 rollouts, the top actions were socialize_initiate, eat_slow, exercise_intense, giving partial alignment. The rollout captures one intended behavior but also exposes a competing policy bias.

- Authored persona: A retiree who walks and eats at the same time every day. He dislikes change and finds his stability in keeping a fixed routine, and treats cleanliness and tidiness as priorities.
- Bar chart: `results/designer_persona_case_study/action_bars/48_routine-driven_retiree.png`

### quiet family caretaker

This persona was authored from Low E + High A + High C as a 부모를 돌보는 가족. The expected behavioral signature was clean, socialize_respond, rest_alone. Across five v3 rollouts, the top actions were rest_alone, socialize_respond, focused_work, giving strong alignment. The policy mostly preserves the designer-authored behavioral intent.

- Authored persona: A quiet family member who lives alongside her aging parents. She spends more of her day adjusting to their condition and schedule than to her own, and steadies herself with even brief moments of solitary rest.
- Bar chart: `results/designer_persona_case_study/action_bars/49_quiet_family_caretaker.png`

### restless rideshare driver

This persona was authored from Mid E + High N + Mid C as a 불안정한 라이드셰어 기사. The expected behavioral signature was eat_quick, nap, move_right. Across five v3 rollouts, the top actions were socialize_initiate, sleep, rest_with_others, giving weak alignment (F2_style_reward_conflict). This is a useful negative case where the embedding/policy pair does not cleanly express the authored archetype.

- Authored persona: A rideshare driver with an erratic schedule. He handles customers well but is constantly thinking about the next ride and his earnings, and uses brief naps and quick meals to keep himself going whenever a gap opens up.
- Bar chart: `results/designer_persona_case_study/action_bars/50_restless_rideshare_driver.png`
