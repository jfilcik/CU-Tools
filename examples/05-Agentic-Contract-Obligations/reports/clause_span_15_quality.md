# Agentic CUAD clause-span benchmark

This benchmark evaluates category-specific exact-span extraction against official CUAD annotations. Failed documents contribute all gold spans and zero predictions.

## Summary

| Metric | Result |
|---|---:|
| Completed | 13/15 |
| Active execution time | 17.84 hours |
| Analysis attempts including retries | 28 |
| Mean completed latency | 8.3 min |
| Gold spans | 875 |
| Predicted spans | 643 |
| Matched spans | 207 |
| Precision | 32.2% |
| Recall | 23.7% |
| F1 | 27.3% |
| Source groundedness | 90.5% |
| Input tokens | 5,397,054 |
| Output tokens | 802,879 |

## Per-category quality

| Category | Predicted | Gold | Matched | Precision | Recall | F1 | Grounded |
|---|---:|---:|---:|---:|---:|---:|---:|
| Affiliate License-Licensee | 7 | 11 | 1 | 14.3% | 9.1% | 11.1% | 85.7% |
| Affiliate License-Licensor | 5 | 16 | 3 | 60.0% | 18.8% | 28.6% | 80.0% |
| Anti-Assignment | 34 | 48 | 9 | 26.5% | 18.8% | 22.0% | 85.3% |
| Audit Rights | 40 | 95 | 10 | 25.0% | 10.5% | 14.8% | 95.0% |
| Change Of Control | 15 | 30 | 3 | 20.0% | 10.0% | 13.3% | 100.0% |
| Competitive Restriction Exception | 43 | 20 | 7 | 16.3% | 35.0% | 22.2% | 97.7% |
| Covenant Not To Sue | 9 | 16 | 4 | 44.4% | 25.0% | 32.0% | 100.0% |
| Exclusivity | 52 | 31 | 8 | 15.4% | 25.8% | 19.3% | 100.0% |
| Insurance | 44 | 85 | 20 | 45.5% | 23.5% | 31.0% | 90.9% |
| Ip Ownership Assignment | 15 | 33 | 3 | 20.0% | 9.1% | 12.5% | 93.3% |
| Irrevocable Or Perpetual License | 15 | 15 | 11 | 73.3% | 73.3% | 73.3% | 93.3% |
| Joint Ip Ownership | 4 | 15 | 2 | 50.0% | 13.3% | 21.1% | 100.0% |
| License Grant | 51 | 76 | 30 | 58.8% | 39.5% | 47.2% | 88.2% |
| Liquidated Damages | 16 | 13 | 7 | 43.8% | 53.8% | 48.3% | 81.2% |
| Minimum Commitment | 22 | 40 | 9 | 40.9% | 22.5% | 29.0% | 86.4% |
| Most Favored Nation | 1 | 4 | 0 | 0.0% | 0.0% | 0.0% | 100.0% |
| No-Solicit Of Customers | 6 | 10 | 4 | 66.7% | 40.0% | 50.0% | 100.0% |
| No-Solicit Of Employees | 9 | 14 | 7 | 77.8% | 50.0% | 60.9% | 88.9% |
| Non-Compete | 31 | 48 | 16 | 51.6% | 33.3% | 40.5% | 87.1% |
| Non-Disparagement | 1 | 7 | 1 | 100.0% | 14.3% | 25.0% | 100.0% |
| Non-Transferable License | 17 | 26 | 9 | 52.9% | 34.6% | 41.9% | 88.2% |
| Post-Termination Services | 94 | 57 | 13 | 13.8% | 22.8% | 17.2% | 87.2% |
| Price Restrictions | 21 | 8 | 1 | 4.8% | 12.5% | 6.9% | 85.7% |
| Revenue/Profit Sharing | 34 | 35 | 9 | 26.5% | 25.7% | 26.1% | 82.4% |
| Rofr/Rofo/Rofn | 21 | 58 | 5 | 23.8% | 8.6% | 12.7% | 85.7% |
| Source Code Escrow | 7 | 21 | 1 | 14.3% | 4.8% | 7.1% | 100.0% |
| Termination For Convenience | 6 | 13 | 5 | 83.3% | 38.5% | 52.6% | 83.3% |
| Third Party Beneficiary | 8 | 7 | 5 | 62.5% | 71.4% | 66.7% | 100.0% |
| Unlimited/All-You-Can-Eat-License | 2 | 2 | 0 | 0.0% | 0.0% | 0.0% | 100.0% |
| Volume Restriction | 6 | 5 | 1 | 16.7% | 20.0% | 18.2% | 83.3% |
| Warranty Duration | 7 | 16 | 3 | 42.9% | 18.8% | 26.1% | 100.0% |

## Per-document quality

| Document | Status | Predicted | Gold | Matched | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|
| gooseheadinsurance-inc-04-02-2018-ex-10-6-franch-c9222751 | success | 115 | 79 | 30 | 26.1% | 38.0% | 30.9% |
| mrsfieldsoriginalcookiesinc-01-29-1998-ex-10-fra-7714bf63 | success | 49 | 63 | 12 | 24.5% | 19.0% | 21.4% |
| playboyenterprisesinc-20090220-10-qa-ex-10-2-409-0ec4ad16 | failed | 0 | 58 | 0 | 0.0% | 0.0% | 0.0% |
| cardlyticsinc-20180112-s-1-ex-10-16-11002987-ex--d108d8a9 | success | 51 | 82 | 19 | 37.3% | 23.2% | 28.6% |
| buffalowildwingsinc-06-05-1998-ex-10-3-franchise-d3ecacf8 | success | 50 | 74 | 14 | 28.0% | 18.9% | 22.6% |
| array-biopharma-inc-license-development-and-comm-a0e14c30 | success | 48 | 54 | 16 | 33.3% | 29.6% | 31.4% |
| corioinc-07-20-2000-ex-10-5-license-and-hosting--9425f23a | success | 27 | 38 | 9 | 33.3% | 23.7% | 27.7% |
| upjohninc-20200121-10-12g-ex-2-6-11948692-ex-2-6-66e33fbe | success | 45 | 72 | 17 | 37.8% | 23.6% | 29.1% |
| harpoontherapeuticsinc-20200312-10-k-ex-10-18-12-e3e3aa71 | success | 44 | 59 | 16 | 36.4% | 27.1% | 31.1% |
| monsanto-company-second-a-r-exclusive-agency-and-412f6a03 | success | 81 | 79 | 25 | 30.9% | 31.6% | 31.3% |
| aurasystemsinc-06-16-2010-ex-10-25-strategic-all-8f073bd5 | success | 26 | 30 | 14 | 53.8% | 46.7% | 50.0% |
| healthgatedatacorp-11-24-1999-ex-10-1-hosting-an-c72abcf3 | success | 24 | 36 | 9 | 37.5% | 25.0% | 30.0% |
| aimmunetherapeuticsinc-20200205-8-k-ex-10-3-1196-daa14554 | success | 34 | 43 | 13 | 38.2% | 30.2% | 33.8% |
| jointcorp-09-19-2014-ex-10-15-franchise-agreemen-464a6b22 | success | 49 | 69 | 13 | 26.5% | 18.8% | 22.0% |
| ritterpharmaceuticalsinc-20200313-s-4a-ex-10-54--3e241e19 | failed | 0 | 39 | 0 | 0.0% | 0.0% | 0.0% |
