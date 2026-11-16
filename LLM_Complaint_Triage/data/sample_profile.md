# Complaint slice audit

Source: `CCDB_Export_13_September_2025_through_October_2025.csv`. Source SHA-256: `acdfdbb8df320c829479a63c55f79364b3e3b3c4c9ab5878d13e25575b70b785`.
Sample SHA-256: `1e8cd5d96734a027988267f59c74a921a1a69cb2c89a96d4591796c358812be1`.

Uniform reservoir sample without replacement; seed **42**; **500 records**. Eligibility: narrative is nonempty after stripping whitespace. No category, company, date, length, or outcome filter; no balancing, deduplication, or rerolling. All original columns and cell values are preserved; selected rows are written in source order.

Full export: **1,023,636** rows. Narrative-eligible: **157,821** (**15.42%**); excluded blank narratives: **865,815**.

Observed received dates: full export **2025-09-01 to 2025-10-31**; eligible **2025-09-01 to 2025-10-31**; sample **2025-09-01 to 2025-10-31**. These are received dates, which need not match the archive filename's period.

## Findings

- Product: sample covers **11 of 11** eligible values. Largest: **Credit reporting or other personal consumer reports**, 343/500 (**68.60%**); top three share **87.40%**. Total variation distance from eligible data: **0.0542**.
- No individual product differs from its eligible share by 5 percentage points or more.
- Company: sample covers **89 of 1709** eligible values. Largest: **TRANSUNION INTERMEDIATE HOLDINGS, INC.**, 121/500 (**24.20%**); top three share **69.80%**. Total variation distance from eligible data: **0.1551**.
- No individual company differs from its eligible share by 5 percentage points or more.
- Duplicate Complaint IDs: eligible **0**, sample **0**. Repeated exact narrative texts after whitespace trimming (extra rows beyond first occurrence): eligible **71711**, sample **68** (**13.60%** of sample rows). No duplicates were removed.

Repeated narratives reduce text diversity and can cause leakage if later evaluation splits place the same text in different sets. This audit counts exact matches after trimming only; it does not detect near-duplicates.

A random slice can faithfully inherit substantial source concentration. Compare full-export versus eligible shares below to see selection associated with narrative availability, and eligible versus sample shares to see sampling variation. The 5-point flag is descriptive, not a significance test or a pass/fail criterion. At n=500 the worst-case approximate 95% margin for a single random-sample share is +/-4.38 percentage points (before finite-population correction). Many rare values will be absent, especially companies; this does not establish coverage of all routing or sensitive-case types.

This audit assesses observed mix within this export, not representativeness of all CFPB complaints or PayGuard customers. Narrative availability and the archive window limit that inference. Product and Issue are existing metadata, not validated triage labels. No LLM triage or manual correctness evaluation was performed.

## Product

| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Credit reporting or other personal consumer reports | 921,842 (90.06%) | 114,268 (72.40%) | 343 (68.60%) | -3.80 |
| Debt collection | 52,363 (5.12%) | 17,065 (10.81%) | 63 (12.60%) | +1.79 |
| Credit card | 15,917 (1.55%) | 7,446 (4.72%) | 31 (6.20%) | +1.48 |
| Checking or savings account | 12,449 (1.22%) | 6,942 (4.40%) | 16 (3.20%) | -1.20 |
| Money transfer, virtual currency, or money service | 6,698 (0.65%) | 4,268 (2.70%) | 15 (3.00%) | +0.30 |
| Mortgage | 4,112 (0.40%) | 2,284 (1.45%) | 14 (2.80%) | +1.35 |
| Vehicle loan or lease | 3,510 (0.34%) | 1,950 (1.24%) | 8 (1.60%) | +0.36 |
| Payday loan, title loan, personal loan, or advance loan | 2,423 (0.24%) | 1,403 (0.89%) | 4 (0.80%) | -0.09 |
| Student loan | 2,639 (0.26%) | 1,213 (0.77%) | 3 (0.60%) | -0.17 |
| Prepaid card | 1,012 (0.10%) | 568 (0.36%) | 1 (0.20%) | -0.16 |
| Debt or credit management | 671 (0.07%) | 414 (0.26%) | 2 (0.40%) | +0.14 |

## Company

| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| EQUIFAX, INC. | 329,025 (32.14%) | 41,573 (26.34%) | 120 (24.00%) | -2.34 |
| TRANSUNION INTERMEDIATE HOLDINGS, INC. | 315,875 (30.86%) | 39,373 (24.95%) | 121 (24.20%) | -0.75 |
| Experian Information Solutions Inc. | 256,332 (25.04%) | 32,154 (20.37%) | 108 (21.60%) | +1.23 |
| CAPITAL ONE FINANCIAL CORPORATION | 4,954 (0.48%) | 1,982 (1.26%) | 8 (1.60%) | +0.34 |
| JPMORGAN CHASE & CO. | 4,105 (0.40%) | 1,793 (1.14%) | 9 (1.80%) | +0.66 |
| WELLS FARGO & COMPANY | 3,455 (0.34%) | 1,450 (0.92%) | 6 (1.20%) | +0.28 |
| CITIBANK, N.A. | 3,428 (0.33%) | 1,446 (0.92%) | 8 (1.60%) | +0.68 |
| Chime Financial Inc | 2,206 (0.22%) | 1,446 (0.92%) | 2 (0.40%) | -0.52 |
| Block, Inc. | 2,256 (0.22%) | 1,425 (0.90%) | 7 (1.40%) | +0.50 |
| BANK OF AMERICA, NATIONAL ASSOCIATION | 3,224 (0.31%) | 1,322 (0.84%) | 7 (1.40%) | +0.56 |
| Resurgent Capital Services L.P. | 4,287 (0.42%) | 1,212 (0.77%) | 2 (0.40%) | -0.37 |
| CL Holdings LLC | 2,843 (0.28%) | 807 (0.51%) | 4 (0.80%) | +0.29 |
| LEXISNEXIS | 3,794 (0.37%) | 589 (0.37%) | 1 (0.20%) | -0.17 |
| CBC Companies, Inc. | 4,631 (0.45%) | 514 (0.33%) | 2 (0.40%) | +0.07 |

## Issue

| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Incorrect information on your report | 545,646 (53.30%) | 60,088 (38.07%) | 177 (35.40%) | -2.67 |
| Improper use of your report | 206,603 (20.18%) | 36,015 (22.82%) | 110 (22.00%) | -0.82 |
| Problem with a company's investigation into an existing problem | 167,581 (16.37%) | 18,892 (11.97%) | 62 (12.40%) | +0.43 |
| Attempts to collect debt not owed | 19,064 (1.86%) | 7,273 (4.61%) | 35 (7.00%) | +2.39 |
| Written notification about debt | 12,134 (1.19%) | 4,526 (2.87%) | 9 (1.80%) | -1.07 |
| Managing an account | 7,025 (0.69%) | 3,883 (2.46%) | 11 (2.20%) | -0.26 |
| False statements or representation | 7,391 (0.72%) | 2,521 (1.60%) | 13 (2.60%) | +1.00 |
| Problem with a purchase shown on your statement | 3,432 (0.34%) | 1,869 (1.18%) | 6 (1.20%) | +0.02 |
| Other transaction problem | 2,322 (0.23%) | 1,534 (0.97%) | 6 (1.20%) | +0.23 |
| Took or threatened to take negative or legal action | 11,034 (1.08%) | 1,384 (0.88%) | 2 (0.40%) | -0.48 |
| Problem with fraud alerts or security freezes | 3,884 (0.38%) | 660 (0.42%) | 2 (0.40%) | -0.02 |
| Closing your account | 1,083 (0.11%) | 571 (0.36%) | 5 (1.00%) | +0.64 |

## Received month

| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025-09 | 503,850 (49.22%) | 81,660 (51.74%) | 266 (53.20%) | +1.46 |
| 2025-10 | 519,786 (50.78%) | 76,161 (48.26%) | 234 (46.80%) | -1.46 |

## State

| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| TX | 155,617 (15.20%) | 25,420 (16.11%) | 87 (17.40%) | +1.29 |
| FL | 147,836 (14.44%) | 18,366 (11.64%) | 72 (14.40%) | +2.76 |
| CA | 95,436 (9.32%) | 16,566 (10.50%) | 39 (7.80%) | -2.70 |
| GA | 79,161 (7.73%) | 12,656 (8.02%) | 44 (8.80%) | +0.78 |
| IL | 45,389 (4.43%) | 7,473 (4.74%) | 17 (3.40%) | -1.34 |
| NY | 52,431 (5.12%) | 7,408 (4.69%) | 27 (5.40%) | +0.71 |
| NC | 36,963 (3.61%) | 6,476 (4.10%) | 15 (3.00%) | -1.10 |
| PA | 32,671 (3.19%) | 4,634 (2.94%) | 13 (2.60%) | -0.34 |
| LA | 24,951 (2.44%) | 4,324 (2.74%) | 15 (3.00%) | +0.26 |
| SC | 25,205 (2.46%) | 4,288 (2.72%) | 11 (2.20%) | -0.52 |
| NJ | 29,013 (2.83%) | 4,197 (2.66%) | 15 (3.00%) | +0.34 |
| MI | 21,309 (2.08%) | 3,725 (2.36%) | 17 (3.40%) | +1.04 |
| AL | 28,432 (2.78%) | 3,170 (2.01%) | 14 (2.80%) | +0.79 |

## Submitted via

| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Web | 1,017,505 (99.40%) | 157,821 (100.00%) | 500 (100.00%) | +0.00 |
| Phone | 2,480 (0.24%) | 0 (0.00%) | 0 (0.00%) | +0.00 |
| Postal mail | 1,568 (0.15%) | 0 (0.00%) | 0 (0.00%) | +0.00 |
| Referral | 2,083 (0.20%) | 0 (0.00%) | 0 (0.00%) | +0.00 |

## Narrative length

| Value | Full export n (%) | Eligible n (%) | Sample n (%) | Sample - eligible (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| 250-999 | 77,500 (7.57%) | 77,500 (49.11%) | 240 (48.00%) | -1.11 |
| 1000-2999 | 50,744 (4.96%) | 50,744 (32.15%) | 170 (34.00%) | +1.85 |
| 1-249 | 21,859 (2.14%) | 21,859 (13.85%) | 60 (12.00%) | -1.85 |
| 3000+ | 7,718 (0.75%) | 7,718 (4.89%) | 30 (6.00%) | +1.11 |
| 0 (blank) | 865,815 (84.58%) | 0 (0.00%) | 0 (0.00%) | +0.00 |

Company, Issue, and State tables show the union of the top ten values in each population. The JSON report includes complete counts and comparisons for every dimension, including Sub-product, Tags, and Company response to consumer.
