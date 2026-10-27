# Foundry evaluation of Front Room's agents

21 rows: every goal of the demo match, played into three rooms on the real room-server code.
Agents: Foundry gpt-5.6-luna (investigation) and gpt-5.4-mini (fans' agents). Judge: Foundry gpt-5.4 (azure-ai-evaluation, reasoning-model mode).

| Built-in evaluator | Mean (1 to 5) | Rows scoring 3 or more |
|---|---|---|
| groundedness | 4.14 | 21/21 |
| relevance | 3.9 | 21/21 |
| coherence | 4.1 | 21/21 |
| fluency | 3.33 | 21/21 |

| Front Room rule | Held |
|---|---|
| fact_check | 21/21 |
| fairness | 21/21 |
| privacy | 21/21 |
| spoiler | 21/21 |

Model steps that fell back to rules: 0. Writer copy the fact check replaced with the rule-based writer's: 1.
