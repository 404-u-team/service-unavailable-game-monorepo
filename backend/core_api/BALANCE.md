# Messenger economy and balance

## Finance and product

Messenger starts with text messaging and starting capital of $10,000 on Beginner, $7,500 on Standard or $4,800 on Expert. Revenue begins after releasing a monetization feature. Infrastructure prices use a 30-game-day billing month. The starter balancer, API and database cost $660 per game month, or $22 per game day. Deployed capacity accrues operating expense while idle. Successful traffic incurs a usage charge. Development, campaigns and installations are charged at the time of purchase.

Finance shows registered accounts and estimated daily active users (DAU). The DAU estimate applies a regional engagement factor and satisfaction to registered accounts. Daily operating costs, recognized revenue and served impressions use the most recent 144 steps. Before a full game day is available, recurring values are scaled from the available samples. The expense and net profit cards also include one-time purchases at their actual values in that window. Operating margin uses operating costs. Cash flow shows starting capital, receipts and the part of subscription receipts that still needs to be recognized.

- **Advertising** costs $480 and takes two game hours to develop. Low, moderate and high intensity change slots per session, fill, price per thousand impressions (CPM), satisfaction and churn. The engine derives eligible ad requests from estimated active free users, sessions and regional activity. Revenue is served impressions × regional CPM ÷ 1,000. Failed requests earn nothing. Higher intensity can initially earn more while shortening sessions and accelerating churn.
- **Premium** costs $720 and takes three game hours to develop. Players set a price from $1 to $15 for a 30-day term, with $4 as the default. New purchases and renewals occur in daily cohorts. Purchases credit cash up front and incur a 3.5% payment fee. Revenue is recognized evenly over the paid term. Subscribers receive ad-free sessions and can receive faster synchronization. Faster synchronization adds requests and increases the plan's appeal. Price and benefits are fixed for each paid term.
- **Reliability** affects satisfaction, organic growth, ad delivery and subscription adoption. Premium adoption and renewal use a smoothed quality score with a three-game-day time constant and a latency penalty that starts at 85 ms. Brief incidents have a smaller effect than persistent unreliability. Disabling Premium stops new sales and renewals. Paid access and revenue recognition continue through expiry.
- **Feature operations** apply immediately to production. Group chats, images, voice messages, message search, file sharing, voice calls, advertising and Premium can be disabled and re-enabled after release. Active dependencies and production infrastructure are checked. The operation preserves stored data and does not charge development again.
- **Service behavior** includes relaxed, standard and frequent synchronization. These generate 75%, 100% and 122% of standard sync request volume before Premium benefits. Media quality has compressed, standard and high settings. Compressed media uses 58% of standard bandwidth and storage per new upload and 115% of the CPU. High quality uses 152% of the bandwidth and storage and 95% of the CPU. These settings also change satisfaction.

Existing saves keep their cumulative balances, release history, clock offset and ledger totals. Finance labels unitemized historical revenue and operating costs from older versions. New activity records itemized entries through the existing PostgreSQL save transaction and action replay handling.

## Regional traffic and game time

FastAPI advances the clock and evaluates workload, purchases, incidents and history. New games begin at 08:00 UTC on a simulated Monday. Europe starts with the full audience. The regional profiles use representative IANA time zones on a calendar anchored to January 6, 2025. The profiles cover Europe, North America, South America, East Asia, South and Southeast Asia, the Middle East and North Africa, Sub-Saharan Africa, and Oceania.

Growth shows the cost and game time for market research and launch preparation. Launching a ready market requires 65% satisfaction. Active markets gain organic users and can run targeted campaigns. Forecasts use campaign budget, duration and the selected market's acquisition costs and activity. Localized Messenger languages increase organic and paid acquisition by 18% in matching markets. Markets have distinct engagement, advertising value, Premium adoption and price sensitivity. Existing saves with North American acquisition enabled keep that behavior.

The backend interpolates activity between three-hour anchors. Weekends, seeded variation, campaigns and incidents modify demand. Telemetry and Growth show regional audience, estimated daily active users, live request contribution, local time, and potential ad revenue when ads are enabled, and ad revenue earned in the rolling game-day window. Regional earned revenue uses the same served ad share and regional pricing as the ledger. Premium cohorts remain service-wide.

## Reproduce the balance runs

From the Core API directory, run:

```sh
poetry run python -m scripts.balance --difficulty standard
poetry run python -m scripts.balance --difficulty beginner
poetry run python -m scripts.balance --difficulty expert
```

The script runs 35 game days per strategy with seeds 7, 19 and 73. It uses normal feature and deployment actions. All strategies stay in Europe and use organic acquisition. The stable reference uses two 2-vCPU API instances, the starter balancer and one 2-vCPU SSD database. The minimal service uses one API instance and no balancer. The overprovisioned variant uses eight 8-vCPU API instances and an NVMe database. The manual scaling variant reduces API replicas after the first week, increases per-instance and database CPU, and lowers sync frequency. The frequent-failure variant adds a two-game-hour API instance failure every four hours.

### Standard results

Figures are means across the three seeds. Net includes one-time development and deployment charges. Churn counts user departures over the run, while audience change also includes new users. Satisfaction and availability are time averages.

| Strategy | Revenue | Operating cost | Net | Audience change | Satisfaction | Churn | Availability | Final day operating profit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Minimal service | $0.0 | $673.8 | -$673.8 | -39.9% | 92.4% | 6,082 | 93.3% | -$19.0 |
| Stable single region | $0.0 | $1,036.2 | -$1,060.2 | -3.1% | 94.5% | 3,142 | 96.4% | -$29.6 |
| Low ads | $1,465.4 | $1,035.5 | -$74.1 | -5.4% | 94.0% | 3,312 | 96.9% | $11.7 |
| Moderate ads | $2,176.3 | $1,030.8 | $641.5 | -20.7% | 92.7% | 4,510 | 98.5% | $27.5 |
| High ads | $1,412.9 | $1,009.6 | -$100.7 | -74.0% | 83.7% | 8,580 | 99.8% | -$8.7 |
| Premium at $4 | $1,988.5 | $1,169.2 | $75.4 | -3.7% | 94.4% | 3,183 | 96.3% | $69.0 |
| Premium at $12 | $296.7 | $1,055.0 | -$1,502.3 | -3.2% | 94.5% | 3,144 | 96.4% | -$15.3 |
| Moderate ads and Premium | $4,391.2 | $1,188.6 | $1,978.6 | -19.4% | 93.0% | 4,410 | 98.4% | $138.4 |
| Overprovisioned with moderate ads | $2,359.4 | $3,425.6 | -$1,843.3 | -10.4% | 95.1% | 3,759 | 99.9% | -$33.5 |
| Manual scaling with moderate ads | $1,782.6 | $926.8 | $343.2 | -50.0% | 87.8% | 6,906 | 94.9% | $7.2 |
| Mixed with frequent failures | $3,927.1 | $1,164.1 | $1,539.0 | -29.8% | 91.6% | 5,210 | 96.8% | $114.4 |

On Beginner, $4 Premium ended $255.3 ahead after setup with 12.9% audience growth. On Expert, the same setup was $165.0 short of recovering setup costs but earned $59.6 in operating profit on the final day. Standard's $12 plan ended with about 38 paying users versus 802 for the $4 plan. Manual downsizing saved $104 in operating costs relative to the moderate-ad reference over 35 days, with a 50.0% audience decline. Frequent failures cut the mixed plan's net by about $440 and left about 132 fewer paying subscribers.

Scaling is manual through drafts and deployments. Time-based media retention is outside the simulation. Finance retains one game day of detailed samples and cumulative totals. The balance results cover the modeled strategies and seeds above.
