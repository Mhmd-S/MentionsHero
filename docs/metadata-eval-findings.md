# Metadata Extraction — OLD vs NEW Eval

_Generated 2026-06-12T16:30:47.980973+00:00 from `backend/scripts/eval_metadata.py` (persona=Donald Trump, sample=35, seed=42)._

NEW = single grounded Gemini call (Google Search) + deterministic event_type guardrail. OLD = the existing `event_tags` rows (DDG + two title-centric calls).

## Headline

| Metric | OLD | NEW |
|---|---|---|
| event_type = `other` rate |   71% |    0% |
| venue fill-rate |   46% |  100% |
| city fill-rate |   49% |  100% |
| state fill-rate |   46% |   83% |
| country fill-rate |   49% |  100% |

- OLD rows present for 35/35 sampled transcripts (0 manually-confirmed, excluded from 'dumb LLM' judgement).
- NEW event_type source: deterministic=27, llm=8, none=0; deterministic guardrail resolved 27/35 titles outright.
- NEW extraction failures (`_llm_failed`): 0/35.

## Speed & cost (NEW)

- per-transcript wall-clock: mean 4.9s, p95 7.1s (single grounded call; OLD made a DDG round-trip + 2 calls).
- tokens: 40,113 prompt + 6,503 completion ≈ $0.0050 token cost (+ per-request Google Search grounding billing, not counted here).

## event_type rescues (OLD `other`/missing → NEW specific): 25

- `other` → **`signing_ceremony`** (deterministic) — President Trump Participates in a Signing with the Prime Ministers of Cambodia and Thailand
- `other` → **`prepared_remarks`** (deterministic) — President Trump Delivers Remarks, May 22, 2026 2026-05-22 19:18
- `other` → **`signing_ceremony`** (deterministic) — President Trump Signs an Executive Order, Dec. 18, 2025
- `other` → **`roundtable`** (deterministic) — President Trump Participates in the Memphis Safe Task Force Roundtable
- `other` → **`press_conference`** (llm) — President Trump Gaggles with Press on Air Force One En Route Palm Beach, FL, Feb. 6, 2026
- `other` → **`ceremony`** (deterministic) — President Trump Delivers Remarks at the Greek Independence Day Celebration
- `other` → **`bilateral_meeting`** (deterministic) — President Trump Participates in a Bilateral Meeting, May 7, 2026 2026-05-07 15:47
- `other` → **`troop_address`** (deterministic) — President Trump Participates in a Call with Service Members
- `other` → **`prepared_remarks`** (deterministic) — President Trump Participates in a Wreath Laying Ceremony and Delivers Remarks 2026-05-25 16:18
- `other` → **`ceremony`** (deterministic) — President Trump and the First Lady Arrive at the Kennedy Center Honors
- `other` → **`signing_ceremony`** (llm) — President Trump Participates in a Working Session with U.S. - ASEAN Leaders
- `other` → **`prepared_remarks`** (deterministic) — President Trump Delivers Remarks at the America Business Forum Miami
- `other` → **`greeting`** (deterministic) — President Trump Participates in a Greeting with the President of the People's Republic of China 2026-05-14 02:18
- `other` → **`signing_ceremony`** (deterministic) — President Trump Signs Senate Amendment to H.R. 5371
- `other` → **`prepared_remarks`** (deterministic) — President Trump Delivers Remarks to NCAA Collegiate National Champions
- `other` → **`prepared_remarks`** (deterministic) — President Trump Delivers Remarks to Fort Bragg Military Families
- `other` → **`troop_address`** (deterministic) — President Trump Participates in a Troop Visit and Remarks on the USS George Washington
- `other` → **`summit`** (llm) — President Trump Participates in the Board of Peace Event
- `other` → **`ceremony`** (llm) — President Trump Participates in a High Honor Presentation
- `other` → **`prepared_remarks`** (llm) — President Donald J. Trump’s 2026 State of the Union Address
- `other` → **`ceremony`** (llm) — President Trump Participates in the Friends of Ireland Luncheon
- `other` → **`ceremony`** (llm) — President Trump Participates in a Dinner Hosted by the President of the Republic of Korea
- `other` → **`press_conference`** (deterministic) — President Trump Holds a Press Conference, Apr. 6, 2026
- `other` → **`ceremony`** (deterministic) — President Trump Attends the State Department Kennedy Center Honors Medal Presentation Dinner
- `other` → **`press_conference`** (llm) — President Trump Participates in a Site Visit at Thermo Fisher Scientific

## OLD → NEW transition counts

| OLD | NEW | n |
|---|---|---|
| other | prepared_remarks | 6 |
| other | ceremony | 6 |
| other | signing_ceremony | 4 |
| other | press_conference | 3 |
| bilateral_meeting | bilateral_meeting | 2 |
| roundtable | roundtable | 2 |
| other | troop_address | 2 |
| prepared_remarks | prepared_remarks | 2 |
| other | roundtable | 1 |
| other | bilateral_meeting | 1 |
| cabinet_meeting | cabinet_meeting | 1 |
| other | greeting | 1 |
| signing_ceremony | signing_ceremony | 1 |
| reception | reception | 1 |
| other | summit | 1 |
| announcement | announcement | 1 |
