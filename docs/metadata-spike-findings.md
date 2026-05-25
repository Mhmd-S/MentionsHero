# Metadata Extraction Spike — Findings

_Generated 2026-05-24T08:54:29.154896+00:00 from `backend/scripts/metadata_extraction_spike.py`._

## Per-transcript results

### 1. President Trump Delivers an Address to the Nation, Dec. 17, 2025

- **URL:** https://www.youtube.com/watch?v=DpLvGmPetds
- **DB upload_date:** `20251218`
- **yt-dlp title:** President Trump Delivers an Address to the Nation, Dec. 17, 2025
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20251218
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2025-12-18T02:29:18+00:00 (UTC) — HH:MM = 02:29
- **release_timestamp (stream start):** 2025-12-18T01:52:21+00:00 (UTC) — HH:MM = 01:52
- **best event-time source:** `release_timestamp` → 2025-12-18T01:52:21+00:00 (UTC) — HH:MM = 01:52
- **Description length:** 15 chars
  > The White House
- **DDG snippets:** 10 results
  > - Donald Trump - Wikipedia — Donald John Trump is an American politician, media personality, and businessman who is the 47th president of the United States. A member of the Republican Party, he served as the 45th president from 2017 to 2021. - President Trump Delivers an Address to the Nation, Dec. 17 ... December 17, 2025: Address to the Nation | Miller Center Trump Delivers Attacks and Deflects Blame for Americans ... Takeaways from Trump's year-end address to the nation Trump announces dividend to U.S. soldiers in speech - CNBC WATCH: Trump addresses the nation from the White House - PBS — …

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `Diplomatic Reception Room of the White House`
- event_type (title-only): `prepared_remarks` (rule #15) — The title contains 'Address to', which satisfies rule 15 for prepared remarks.
- audience_type: `general`
- event_time_local (LLM): `None`
- confidence: `0.95`
- primary_source: `web`
- reasoning: Web search snippets explicitly identify the Diplomatic Reception Room of the White House as the venue for this televised prime-time address to the nation.

### 2. President Trump's administration is cleaning up DC and making America safe again

- **URL:** https://www.youtube.com/watch?v=kePprHtFUcI
- **DB upload_date:** `20250820`
- **yt-dlp title:** President Trump's administration is cleaning up DC and making America safe again
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20250820
- **live_status:** 'not_live', **was_live:** False
- **timestamp (upload):** 2025-08-20T19:58:58+00:00 (UTC) — HH:MM = 19:58
- **release_timestamp (stream start):** (none)
- **best event-time source:** `timestamp (upload)` → 2025-08-20T19:58:58+00:00 (UTC) — HH:MM = 19:58
- **Description length:** 0 chars
- **DDG snippets:** 10 results
  > - Making the District of Columbia Safe and Beautiful — Mar 28, 2025 · America ’ s capital must be a place in which residents, commuters, and tourists feel safe at all hours, including on public transit. - 75 homeless camps in DC cleared by US Park Police since Trump ... — Aug 15, 2025 · Federal officials have cleared about 75 homeless camps around the nation’s capital under President Trump ’ s effort to clean up Washington , DC — and they’re not done yet. - President Trump is making D.C. streets safe again, including ... — Aug 29, 2025 · President Donald J. Trump promised to restore law and or…

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `None`
- event_type (title-only): `other` (rule #16) — The video title does not contain any of the specific keywords or patterns defined in rules 1 through 15.
- audience_type: `military`
- event_time_local (LLM): `None`
- confidence: `0.9`
- primary_source: `transcript`
- reasoning: The transcript confirms Eric Trump is speaking to National Guard members and police officers in Washington, D.C., though no specific building or venue is named.

### 3. President Trump Delivers Remarks, May 8, 2026

- **URL:** https://www.youtube.com/watch?v=IByVie2qY30
- **DB upload_date:** `20260508`
- **yt-dlp title:** President Trump Delivers Remarks, May 8, 2026
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20260508
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2026-05-08T17:00:03+00:00 (UTC) — HH:MM = 17:00
- **release_timestamp (stream start):** 2026-05-08T15:49:06+00:00 (UTC) — HH:MM = 15:49
- **best event-time source:** `release_timestamp` → 2026-05-08T15:49:06+00:00 (UTC) — HH:MM = 15:49
- **Description length:** 15 chars
  > The White House
- **DDG snippets:** 10 results
  > - President Trump Delivers Remarks, May 8, 2026 - The White House — May 8, 2026 Explore More Videos 17:10 President Trump Delivers Remarks, May 6, 2026 May 6, 2026 07:45 President Trump Gaggles with Press Before Departing the White House, May 8, 2026 - President Trump Delivers Remarks, May 8, 2026 - YouTube — President Trump Delivers Remarks, May 8, 2026 The White House 3.09M subscribers Subscribe - President Trump Delivers Remarks, May 8, 2026 - x.com — The White House (@WhiteHouse). 349 replies. President Trump Delivers Remarks, May 8, 2026 . - LIVE: President Trump Delivers Remarks from the…

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `Rose Garden of the White House`
- event_type (title-only): `prepared_remarks` (rule #15) — The title contains 'Delivers Remarks', which triggers rule 15.
- audience_type: `invited`
- event_time_local (LLM): `10:30`
- confidence: `0.95`
- primary_source: `web`
- reasoning: Web search snippets and the transcript explicitly identify the Rose Garden of the White House and a scheduled time of 10:30 AM.

### 4. President Trump Participates in the Champion of Coal Event

- **URL:** https://www.youtube.com/watch?v=jBfm-1j30eE
- **DB upload_date:** `20260211`
- **yt-dlp title:** President Trump Participates in the Champion of Coal Event
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20260211
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2026-02-11T22:03:01+00:00 (UTC) — HH:MM = 22:03
- **release_timestamp (stream start):** 2026-02-11T21:26:52+00:00 (UTC) — HH:MM = 21:26
- **best event-time source:** `release_timestamp` → 2026-02-11T21:26:52+00:00 (UTC) — HH:MM = 21:26
- **Description length:** 15 chars
  > The White House
- **DDG snippets:** 10 results
  > - LIVE: President Trump Participates in the Champion of Coal — LIVE: President Trump Participates in the Champion of Coal Event – 02/11/26 ... President Trump will host the Champion of Coal Event in the ... - President Trump Participates In Champion Of Coal Event At The — President Donald Trump speaks during an event on the use of coal in the East Room of the White House on February 11, 2026, in Washington, United ... - President Trump Participates In Champion Of Coal Event At The — President Trump Participates In Champion Of Coal Event At The White House - 02/11/2026 ... President Donald Trum…

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `East Room of the White House`
- event_type (title-only): `other` (rule #16) — The title does not contain any of the specific keywords or patterns defined in rules 1 through 15.
- audience_type: `industry`
- event_time_local (LLM): `None`
- confidence: `0.95`
- primary_source: `web`
- reasoning: Web search snippets identify the event's location as the East Room of the White House in Washington, DC, and the audience as coal industry representatives.

### 5. President Trump Delivers Remarks to NCAA Collegiate National Champions

- **URL:** https://www.youtube.com/watch?v=HWsKuI1yyl8
- **DB upload_date:** `20260421`
- **yt-dlp title:** President Trump Delivers Remarks to NCAA Collegiate National Champions
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20260421
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2026-04-21T21:18:38+00:00 (UTC) — HH:MM = 21:18
- **release_timestamp (stream start):** 2026-04-21T20:34:37+00:00 (UTC) — HH:MM = 20:34
- **best event-time source:** `release_timestamp` → 2026-04-21T20:34:37+00:00 (UTC) — HH:MM = 20:34
- **Description length:** 15 chars
  > The White House
- **DDG snippets:** 10 results
  > - LIVE: President Trump delivers remarks to the NCAA Collegiate — LIVE: President Trump delivers remarks to the NCAA Collegiate National Champions ... President Trump delivers remarks to " more than 100 ... - Trump announces he's extending ceasefire - Main Stream — LIVE: President Trump delivers remarks to the NCAA Collegiate National Champions ... President Trump delivers remarks to " more than 100 ... - President Trump honors NCAA Collegiate National Champions at — President Trump honors NCAA Collegiate ... President Trump delivers remarks to NCAA Collegiate National Champions at the White H…

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `The White House`
- event_type (title-only): `prepared_remarks` (rule #15) — The title contains the phrase 'Delivers Remarks', which triggers rule 15 for prepared remarks.
- audience_type: `invited`
- event_time_local (LLM): `None`
- confidence: `0.95`
- primary_source: `transcript`
- reasoning: The transcript and video description explicitly state the event took place at the White House for NCAA champions.

### 6. President Trump Delivers Remarks on the Economy, Dec. 19, 2025

- **URL:** https://www.youtube.com/watch?v=FKU63HY1KJQ
- **DB upload_date:** `20251220`
- **yt-dlp title:** President Trump Delivers Remarks on the Economy, Dec. 19, 2025
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20251220
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2025-12-20T03:36:39+00:00 (UTC) — HH:MM = 03:36
- **release_timestamp (stream start):** 2025-12-20T01:47:31+00:00 (UTC) — HH:MM = 01:47
- **best event-time source:** `release_timestamp` → 2025-12-20T01:47:31+00:00 (UTC) — HH:MM = 01:47
- **Description length:** 15 chars
  > Rocky Mount, NC
- **DDG snippets:** 10 results
  > - President Trump Delivers Remarks on the Economy, Dec. 19, 2025 — President Trump Delivers Remarks on the Economy, Dec. 19, 2025 The White House Watch on - President Trump Delivers Remarks on the Economy, Dec. 19, 2025 — Vice President JD Vance Delivers Remarks in Bangor, Maine President Trump and the First Lady Participate in a Windsor Castle Arrival Ceremony - Full Transcript of President Trump's Speech on the Economy — President Trump delivered an address on the economy from the White House on Wednesday night. The following is a transcript of his remarks , as recorded by The New York Times…

**LLM extraction:**

- city: `Rocky Mount`
- state: `North Carolina`
- county: `Nash`
- venue: `None`
- event_type (title-only): `prepared_remarks` (rule #15) — The title contains the phrase 'Delivers Remarks', which satisfies rule 15.
- audience_type: `supporters`
- event_time_local (LLM): `None`
- confidence: `0.9`
- primary_source: `description`
- reasoning: The video description and specific local news snippets confirm the event took place in Rocky Mount, North Carolina on the specified date, while the transcript's mention of a rally crowd and patriots indicates a supporter audience.

### 7. Operation Epic Fury Update, President Donald J. Trump

- **URL:** https://www.youtube.com/watch?v=AcJC9jOJvk4
- **DB upload_date:** `20260301`
- **yt-dlp title:** Operation Epic Fury Update, President Donald J. Trump
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20260301
- **live_status:** 'not_live', **was_live:** False
- **timestamp (upload):** 2026-03-01T22:03:52+00:00 (UTC) — HH:MM = 22:03
- **release_timestamp (stream start):** (none)
- **best event-time source:** `timestamp (upload)` → 2026-03-01T22:03:52+00:00 (UTC) — HH:MM = 22:03
- **Description length:** 0 chars
- **DDG snippets:** 10 results
  > - Six key lines from Trump 's statement on Iran strikes — ' Operation Epic Fury '. President Trump 's words signal that the scope and scale of the attack will be much larger than the US strike on Iran last summer. - Operation Epic Fury Update , President Donald J . Trump — Decisive Liberty Newsletter Podcast. Operation Epic Fury Update , President Donald J . Trump . 3. 1×. - Operation Epic Fury Update , President Donald J . Trump — President Trump delivers updates about Operation Epic Fury , including the deaths of at least 3 servicemembers.Related Content. President Donald J . Trump on the Un…

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `Oval Office, White House`
- event_type (title-only): `other` (rule #16) — The title does not contain any of the specific keywords or phrases required by rules 1 through 15.
- audience_type: `press`
- event_time_local (LLM): `None`
- confidence: `0.85`
- primary_source: `web`
- reasoning: Web search snippets confirm President Trump provided the update at the White House, specifically mentioning the Oval Office and addressing reporters.

### 8. President Trump Makes an Announcement, Dec. 2, 2025

- **URL:** https://www.youtube.com/watch?v=aGby18D7SOg
- **DB upload_date:** `20251202`
- **yt-dlp title:** President Trump Makes an Announcement, Dec. 2, 2025
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20251202
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2025-12-02T20:38:50+00:00 (UTC) — HH:MM = 20:38
- **release_timestamp (stream start):** 2025-12-02T19:49:27+00:00 (UTC) — HH:MM = 19:49
- **best event-time source:** `release_timestamp` → 2025-12-02T19:49:27+00:00 (UTC) — HH:MM = 19:49
- **Description length:** 15 chars
  > The White House
- **DDG snippets:** 10 results
  > - Donald Trump - Wikipedia — Donald John Trump is an American politician, media personality, and businessman who is the 47th president of the United States. A member of the Republican Party, he served as the 45th president from 2017 to 2021. - President Trump Makes an Announcement, Dec. 2, 2025 — Dec 2 , 2025 · Remarks Research Administration President Donald J. Trump First Lady Melania Trump Vice President JD Vance Second Lady Usha Vance - President Trump Makes an Announcement, Dec. 2, 2025 DVIDS Webcast - President Trump Makes an Announcement, Dec. 2 ... President Trump Makes an Announcement…

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `The White House`
- event_type (title-only): `announcement` (rule #11) — The title contains the phrase 'Makes an Announcement', which triggers rule 11.
- audience_type: `mixed`
- event_time_local (LLM): `None`
- confidence: `0.95`
- primary_source: `web`
- reasoning: Multiple web search snippets and the video description confirm the announcement took place at the White House.

### 9. President Trump Participates in a Call with Service Members

- **URL:** https://www.youtube.com/watch?v=rKVM9pn0RZY
- **DB upload_date:** `20251128`
- **yt-dlp title:** President Trump Participates in a Call with Service Members
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20251128
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2025-11-28T00:26:08+00:00 (UTC) — HH:MM = 00:26
- **release_timestamp (stream start):** 2025-11-27T23:14:12+00:00 (UTC) — HH:MM = 23:14
- **best event-time source:** `release_timestamp` → 2025-11-27T23:14:12+00:00 (UTC) — HH:MM = 23:14
- **Description length:** 14 chars
  > Palm Beach, FL
- **DDG snippets:** 10 results
  > - Trump Holds Call With US Service Members | NTD — President Trump participates in a call with U.S. ... President Donald Trump participates in a call with U.S. ... Trump Rolls Back Biden-Era Fuel ... - Trump Participates in Service Member Calls on Christmas Eve | — President Trump participates in service member calls on Christmas Eve. ... President Donald Trump participates in service member calls at 5:30 p.m. - LIVE NOW: Trump Participates in Service Member Calls on — LIVE NOW: Trump Participates in Service Member Calls on Christmas Eve ... President Donald Trump participates in service membe…

**LLM extraction:**

- city: `Palm Beach`
- state: `Florida`
- county: `Palm Beach`
- venue: `Mar-a-Lago`
- event_type (title-only): `other` (rule #16) — The title does not contain any of the specific keywords or patterns defined in rules 1 through 15, including those related to troop addresses.
- audience_type: `military`
- event_time_local (LLM): `17:30`
- confidence: `0.9`
- primary_source: `web`
- reasoning: Web search snippets and video description place the event at Mar-a-Lago in Palm Beach, Florida, with a start time of 5:30 PM.

### 10. President Trump Delivers Remarks at the House GOP Member Retreat

- **URL:** https://www.youtube.com/watch?v=N6tzCCyfwFM
- **DB upload_date:** `20260106`
- **yt-dlp title:** President Trump Delivers Remarks at the House GOP Member Retreat
- **yt-dlp channel:** The White House
- **yt-dlp upload_date:** 20260106
- **live_status:** 'was_live', **was_live:** True
- **timestamp (upload):** 2026-01-06T16:44:22+00:00 (UTC) — HH:MM = 16:44
- **release_timestamp (stream start):** 2026-01-06T15:02:56+00:00 (UTC) — HH:MM = 15:02
- **best event-time source:** `release_timestamp` → 2026-01-06T15:02:56+00:00 (UTC) — HH:MM = 15:02
- **Description length:** 14 chars
  > Washington, DC
- **DDG snippets:** 10 results
  > - President Trump Delivers Remarks at the House GOP Member ... — President Trump Delivers Remarks on Trump Accounts. January 28, 2026. President Trump Delivers Remarks and Signs Executive Orders at AI Summit. - Trump Delivers Remarks at House GOP Member Retreat | NTD — Recommendations. Trump Speaks to House Republicans About 2026 Agenda, Maduro's Capture. - Watch live: Trump delivers remarks to House GOP member retreat — Watch live coverage as President Trump delivers remarks to the House Republican member retreat at the Kennedy Center. - Category: President Donald Trump delivers remarks at th…

**LLM extraction:**

- city: `Washington`
- state: `District of Columbia`
- county: `None`
- venue: `John F. Kennedy Center for the Performing Arts`
- event_type (title-only): `prepared_remarks` (rule #15) — The title contains 'Delivers Remarks', which matches the pattern for rule 15.
- audience_type: `congress`
- event_time_local (LLM): `None`
- confidence: `0.95`
- primary_source: `web`
- reasoning: Multiple web search snippets identify the Kennedy Center in Washington, D.C. as the specific venue for the 2026 House GOP member retreat.

## Summary

- Sample size: 10
- Extraction errors: 0
- Videos that were livestreams (`was_live=True`): 8/10
- Videos with `timestamp` (upload time): 10/10
- Videos with `release_timestamp` (stream-start time): 8/10

### Fill rate per field

- **city**: 10/10
- **state**: 10/10
- **county**: 2/10
- **venue**: 8/10
- **event_time_local**: 2/10

### Where the location signal came from

- web: 7
- transcript: 2
- description: 1

### Channel distribution

- The White House: 10

## Things to review with the user

- Is the per-field fill rate (especially venue room-level granularity) acceptable?
- For livestream VODs, does `release_timestamp` (stream start) line up with the actual event time better than upload `timestamp`?
- Anything obviously missing from the extracted fields?
