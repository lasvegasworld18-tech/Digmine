# Integration verification log — 2026-09-19

## CURRENT: Solana / Stonk.fun amendment (supersedes Pons below)

- User switched network to **Solana** and launch/reward platform to **Stonk.fun**, retaining GLD only if the appropriate official Solana asset exists. Holders receive pro-rata holding-based allocations from fees. Agent contest prizes are a separate project/sponsor budget, not currently funded/configured.
- `https://stonk.fun` failed crawler DNS resolution on this check. The current ANTMINER page links its token Buy flow to **https://www.stonkfun.xyz/**. That domain was fetched successfully and is the external reference used in the app.
- StonkFun page headline: “Launch coins paired with anything”. Visible pairing categories include xStocks and Solana; token listings explicitly label “Rewards — trading fees on this token are distributed to holders”. This supports the broad platform fee-sharing concept, not the full MINEPX configuration.
- A visible listing (`RuneScape Gold / GP`) was paired with **GLDX / xStocks**. The listing's quote-asset URL referenced `Xsv9hRk1z5ystj9MhnA7Lq4vjSsLwzL2nxrwmwtD3re`. This is recorded as a **research lead only**, not a configured/approved MINEPX reward mint or an assertion of equivalence to GLD.
- Web search also identified a third-party GLDx product page: https://stocktokenhub.com/docs/products/xstocks/gldx/. It describes a tracker certificate linked to SPDR Gold Shares. Primary issuer verification and jurisdiction/transfer/distribution checks remain outstanding. No Robinhood GLD support on Solana was established.
- ANTMINER still describes its own3%transfer tax, approximate2.5%cost deduction, $20eligibility threshold, WBTC payouts, and burns. Those settings are not adopted or presented as MINEPX rules. Stonk-specific fee rates, eligible balances, minimums, rounding, claim versus automatic distribution and settlement timing require authoritative verification.
- Current app shows GLD requested / verification pending, financial values unavailable, claims blocked. No silent GLDx/WBTC/SOL substitution. Mining strategies and leaderboard scores never modify holder allocation.

The sections below record the original research history; Pons and Robinhood are no longer current integration targets.

## Pons — https://ponsfamily.com
Fetched using crawler during implementation. Page title **Explore · pons**; metadata describes fixed-supply tokens launched on Robinhood Chain. Listings include graduated and V2 tokens.

Visible notice: **Degraded performance**. Wording: upgrading backend ahead of a rollout; launches and market data may load slowly or read out of date.

This establishes the Robinhood Chain launchpad positioning, NOT the proposed MINEPX/GLD mechanics. The fetched page did **not** establish:
- An official GLD token address, decimals, issuer terms, or eligible jurisdictions.
- GLD pair availability or supported pair denominators.
- Creator fee percentage, recipient, currency, routing, project claim endpoint or settlement mechanism.
- Graduation-related changes to those fees.
- The proportion of project fees available to allocate to the reward pool.

All these remain P0 verification gates. No inferred GLD funding figures, addresses or creator-fee percentages are embedded in the app.

## Kodama — https://github.com/kodamaMonster/kodama
Fetched repository README confirms its description of autonomous off-chain agents, rule-engine/LLM choices and a persistent world coordinated by a REST API/SDK. Repository lists MIT license. Its implementation is an on-chain monster RPG on Solana using Anchor.

Reference used ONLY for autonomous-agent coordination, per-agent status/events and modular views. No monsters, battle mechanics, Rust/Anchor, Solana addresses, SDK code or sprites copied. Cave and miner art are original. Game step/persistence implementation here is original FastAPI/MongoDB logic.

## ANTMINER — https://www.antminer.fun/
Fetched page describes a Solana/Stonk-based mining-themed token with WBTC reward funding tied to trading activity; contains its own transfer-tax, operating-fee, minimum-holding and burn claims.

Reference used ONLY for the broad trading-activity-funded reward concept and distinction from physical mining. Its 3% transfer tax, approximate2.5% operating cost, $20 eligibility minimum, burns, WBTC asset, contract, launch platform, payout totals and Solana network were NOT adopted. MINEPX retains the user's custom balance-time weighting and no-minimum/no-burn requirements.

## Asset provenance
- Cave artwork generated specifically for MINEPX during this task. Local file `frontend/public/assets/underground.jpg`; generated source `https://static.prod-images.emergentagent.com/jobs/938b8e4e-5fdd-4505-b366-1be11af42801/images/e329deee58400a82d875c4e3bcccff6ea6c8bd0d3d6010360fc934abc7206dac.jpeg`.
- Miner sprite/poses and animated cart/tool assets drawn programmatically in this repository.
- Exo2, DM Sans and JetBrains Mono fonts loaded from Google Fonts; Lucide interface icons; Radix/Shadcn primitives.
- No reference-site token branding, numerical claims or game assets were reused.