# MINEPX — Product Requirements & Handoff

## CURRENT SPECIFICATION — amendment implemented 2026-09-19

**This amendment supersedes the original Robinhood/Pons, balance-time weighting, activation eligibility, Solidity/wagmi plans and fixed-cycle human-agent logic below. Original requirements remain as historical context only where superseded. Preserve the existing visual identity, original mine assets, saved agents and lifetime progress.**

### Latest user request (verbatim)
“Broo ada perubahan pertama kita kembali ke solana jangan robinhood lagi , kedua launch dan fee rewardnya di stonk.fun bukan di ponsfamily lagi, ketiga konsep yg gue buat itu adalah konsep seperti si web antminer tapi ada animasinya pake sistem agent si kodama github, rewards tetap pro rata sesuai holding dari via trading fee, agentnya tampilan mining itu tetap cuma dijadikan pemanis sama buat ada leaderboard untuk contest agent, tambahin beberapa strategi di agent jadi kalau org create agent bisa nambahin strategi atau edit strategi agentnya untuk kontest leaderboard agent mininhgtersebut, jadi tiap agent / tiap akun itu beda beda untuk mining dan scorenya gitu loh sesuai strategi si pegguna untuk agent (kalau bisa buat rumit konsep strategi ini), leaderboard contest itu akan mendapat reward, paham gak maksud gue?”

Confirmed choices:
- “Tetap GLD: hanya jika tersedia aset resmi yang sesuai di Solana.”
- Separate project/sponsor-funded contest pool, not deducted from holder allocations. Build contest/leaderboard first; prize asset, amounts and actual funding are decided later.
- “Preset + editor aturan IF/THEN bertingkat”: priorities, combined conditions, energy, risk, cart load, maintenance; editable without code.
- “Tetap pertahankan yang ada hanya mengubah yang perlu diubah agar sesuai konsep dan untuk tamabahannya juga”.

### Two independent systems
1. **Holder rewards:** Solana + Stonk.fun. Planned share = available holder pool × eligible MINEPX holding / total eligible holdings, subject to verified Stonk distribution mechanics. No game requirement, activation gate, time-held multiplier, per-wallet bonus, or contest-based advantage. No minimum holding is planned by MINEPX, but platform eligibility/rounding must still be verified. No unverified 24-hour settlement promise.
2. **Agent contest:** strategy-driven mining and a leaderboard. A separate project/sponsor prize pool is planned, but no amount, reward asset, payout, or funding is currently configured. No holder pool deductions. Crew bots never enter. Browser profiles are not verified wallets; funded prize eligibility remains gated.

**GLD is unverified on Solana.** Stonk listings of **GLDx** are not evidence that the user's previously requested GLD is the same asset. Do not silently substitute GLDx, WBTC, or SOL, and do not configure an unverified mint.

### Implemented amendment
- Solana/Stonk naming, reward metadata, wallet-readiness dialog, holder formula and Field Guide updated. Original mine/home/crew/art/layout retained. User agent Heti and its accumulated progress preserved; testing-only records cleaned by known IDs.
- Four starting strategy presets: **Wayfinder, Deep Prospector, Steady Hand, Freight Runner**. Creation chooses a preset; advanced editing at `/strategy`, reachable from My Agent.
- Persistent private versioned strategy: target depth1–5, risk0–100, haul threshold20–100, energy reserve10–70, tool repair threshold10–80, and balanced/volume/high-value ore preference.
- Up to8 ordered enabled/disabled rules, up to3 groups per rule and4 numeric conditions per group. ALL/ANY both across groups and within each group. Six comparisons over energy, tool integrity, cart%, depth, vein quality and hazard. Seven user-selectable actions; refining follows a return commitment automatically.
- Strict bounded server validation; duplicate rule IDs and unknown/injected fields rejected. First-match semantics. Mandatory safety for low energy/tools, full cargo and delivery commitment. No arbitrary user code execution.
- Save/discard, reorder/add/delete groups/conditions/rules, version conflict detection, recent version history, tab-local unsaved draft recovery. Edits affect future decisions and preserve live resources, used contest actions and earned score.
- Workbench evaluates60/120/300 decisions in a fixed environment with the same core engine used by live play. Shows score, delivered ore, incidents and decision traces. Does not mutate live agent or leaderboard.
- Strategic live state: energy, tool integrity, cargo/value, depth, quality, hazards, mining/setbacks, returns/refining, recovery/maintenance. Server decisions every18seconds; chosen actions control actual Pixi stage/previous-stage animation and journal reasons. Resident bots retain their familiar ambient cycle.
- Deterministic server clock catches up after browser closure and server restart, up to4000 decisions per pass; optimistic revision update and durable pending-event outbox with unique IDs. Strategy save waits for old decisions to be caught up before applying new rules.
- Public `/leaderboard`: **Brass Hollow Open**, weekly Monday00:00UTC seasons (reasonable initial default), countdown, actual entrants, search, miner detail, rank, score, action usage, rule disclosure and prize status.
- One entry per agent per season, starting100energy/100tools/empty cart/depth1. Budget600 decisions. Joining starts the miner and resets only working resources, not lifetime ore/expeditions/collections. Pause consumes no decisions but does not extend the deadline.
- Score = banked delivered ore value + first-time depth milestones (10 per deeper level, maximum40) − setback penalties (25each), floored at0. Cargo not delivered scores0. No repeated depth farming or empty-delivery farming.
- Score freezes at600decisions or season end; ordinary mining may continue. Previous season entries archived on re-entry. Tie order: score descending, delivered ore descending, actions ascending, entry time ascending, stable agent ID.
- Rankings exclude bots and expose no full private strategy. Top100 displayed; broader pagination and exact out-of-top100 personal rank are future scaling work.
- API rewards explicitly exposes `finances: null`, null financial balances and no fabricated transactions. Claim staysHTTP409. No new external integration or real wallet signature flow was added.

### Amendment architecture / files
- `backend/strategy_models.py`: strict strategy inputs, public game/contest response models.
- `backend/strategies.py`: pure deterministic rule engine, presets and evaluation.
- `backend/game_worker.py`: human-agent migration, catch-up, safety, immutable contest cap/deadline and event outbox.
- `backend/contest_logic.py`: seasons, ranking, archived results.
- `backend/strategy_routes.py`: authenticated strategy read/save/evaluate and contest entry; public presets/leaderboard.
- Existing `server.py`, `engine.py`, `models.py` extended without resetting lifetime state.
- Frontend additions: StrategyPage, RuleBuilder, StrategyEvaluation, ContestPage, AgentTelemetry, strategyTypes and scoped Strategy.css. Existing components updated only for new flows/chain/reward boundaries.
- New collections `strategy_history` (unique version ID), `contest_archive` (unique agent-season ID), indexes on season. Mongo `_id` excluded and public responses typed.

### Verification — amendment
- Iteration2: **28/28 backend tests**, UI flows and six routes at1920×800 and390×844. Follow-up finance metadata key fixed.
- Iteration3: **8/8 targeted engine edge tests** in isolated temporary Mongo databases: 600cap/freeze, repeat-tick idempotence, post-cap ordinary mining, strategy-edit retention, expired paused/active entries, archive/new season, nested-rule semantics, safety/anti-farming and rank ties. Temporary databases removed.
- Main-agent follow-up: guardian evaluation120decisions=1709; freight evaluation120decisions=1742 under same workbench seed, demonstrating genuine outcomes differ. Nested rule edit savedv2, contest entry and long24-character miner-name dialogs verified; no horizontal overflow in final desktop/mobile screenshots.
- References: `test_reports/iteration_2.json`, `test_reports/iteration_3.json`, `backend/tests/test_minepx_strategy_contest.py`, `backend/tests/test_strategy_contest_engine_edges.py`, and `frontend/build-strategy.log`.
- Screenshots: `/app/strategy-desktop-final.jpg`, `/app/strategy-mobile-final.jpg`, `/app/contest-desktop-final.jpg`, `/app/contest-mobile-final.jpg`, `/app/contest-long-name-dialog-mobile.jpg`, `/app/rewards-split-mobile-final.jpg`.

### Current prioritized next steps (replace older backlog below)
**P0 before real rewards:** verify official GLD mint/issuer terms on Solana (or obtain user approval for a distinct alternative); verify Stonk fee settings, denominations, eligibility/minimums, schedule, settlement and jurisdiction; implement real Solana wallet ownership and one-wallet-one-agent binding; decide separate contest prizes/funding/eligibility; add anti-sybil enforcement, immutable season-rule/strategy audit and independent review before funded contests; wire actual holder-fee records and only then verified claims/auto-distribution as platform mechanics require. No EVM/Solidity/wagmi assumption remains.

**P1:** isolated worker leader/scaling controls, replay/reconciliation monitoring and retention; complete historical strategy snapshots/season rule versioning for prize adjudication; pagination and own rank beyond top100; replay/history UI; authenticated access recovery; evaluate rate limits and high-concurrency stress tests.

**P2:** community expeditions, new biomes, cosmetic-only rewards, shareable strategy/result cards, further resource trade-offs and league formats. No paid power or mining multiplier for holder rewards.

---

## Original problem statement

MINEPX — Autonomous Pixel Mining

Web app untuk holder MINEPX: aktifkan penambang pixel, saksikan ekspedisinya, dan terima bagian pool GLD yang didanai trading fee.

Ini rencana konsep dan implementasi, bukan instruksi untuk langsung meluncurkan token.

### Keputusan yang Dikunci
- Chain: Robinhood Chain. Launch platform: https://ponsfamily.com.
- Seluruh konten web berbahasa Inggris: navigasi, onboarding, error, tooltip, notifikasi, dokumentasi pengguna, serta percakapan dan jurnal agent.
- Tidak ada burn, paid boost, monster, atau minimum holding MINEPX.
- Tidak perlu staking atau menyerahkan private key.
- Target pengguna: holder MINEPX yang ingin pengalaman agent otomatis dan pembagian reward transparan.

### User Flow
Hold MINEPX → Connect Wallet → Create Agent → Start Mining → View Rewards → Claim GLD.

Satu agent per wallet. Setelah diaktifkan, agent tetap berjalan ketika browser ditutup. Menjual seluruh MINEPX menghentikan akumulasi reward berikutnya, bukan menghapus hak yang sudah tercatat.

### Konsep Agent dan Tampilan
- Satu tambang bersama dengan kru penambang yang punya kepribadian dan jurnal masing-masing.
- Siklus otomatis: basecamp → survei → menggali → mengangkut ore → refinery → merawat alat.
- Pemain memilih nama, avatar, dan kecenderungan eksplorasi. Penemuan membuka cerita, koleksi, serta kosmetik—bukan pengali reward finansial.
- Agent berinteraksi dan memberi laporan berdasarkan kejadian game nyata. Contoh: “The cart is full. Heading back to the refinery.”
- AI terbatas pada pilihan tindakan game dan narasi. Rule engine mengambil alih jika layanan AI gagal; AI tidak mengendalikan saldo atau wallet.
- Tampilan berbeda dari MONSTA: peta tambang di tengah, My Agent, Agent Journal, Mining Pool, dan Claimable GLD; warna charcoal, brass, dan gold.
- Kodama menjadi referensi pola agent, bukan kode Solana yang langsung dipindahkan. Sprite hanya digunakan ulang bila lisensi aset mengizinkan; selain itu dibuat orisinal.

### Aturan Reward yang Direkomendasikan
- Default awal: periode pembagian 24 jam, tanpa kewajiban login harian.
- Bobot = akumulasi saldo MINEPX × waktu holding setelah agent diaktifkan.
- Reward = GLD tersedia untuk periode × bobot pengguna ÷ total bobot pengguna eligible.
- Gunakan histori transfer on-chain, bukan snapshot sesaat atau skor dari browser.
- Tidak ada bonus tetap per wallet: memecah holding tidak meningkatkan total bagian.
- Ore, level, chat, dan keberuntungan tidak memengaruhi pembagian GLD.
- Pecahan reward diakumulasi dengan presisi tinggi; tidak ada minimum holding terselubung.
- Pool hanya memakai fee yang benar-benar diterima dan dialokasikan. Tanpa pemasukan, tidak ada reward baru; tanpa peserta eligible, dana dibawa ke periode berikutnya.
- Pisahkan Estimated Rewards dan Claimable GLD. Tampilkan sumber fee, saldo pool, periode, rumus, dan transaksi distribusi. Tidak menjanjikan APY atau penambangan emas sungguhan.

### Tech Stack
- React + TypeScript + PixiJS: antarmuka dan dunia pixel.
- FastAPI + worker: simulasi persisten, API, dan pemrosesan event blockchain.
- MongoDB: progres, jurnal, serta ledger perhitungan yang dapat direkonsiliasi.
- Solidity + wagmi/viem: wallet, reward vault, dan klaim GLD di Robinhood Chain.
- LLM server-side opsional: narasi bahasa Inggris, dengan batas biaya dan fallback.

### Urutan Implementasi dan Pengamanan
1. Validasi integrasi: pastikan kontrak GLD resmi, dukungan pair di Pons, penerima/denominasi fee, mekanisme claim, dan perubahan fee setelah graduation. Tentukan persentase fee proyek untuk pool dan batas distribusi Stock Token menurut yurisdiksi.
2. Prototype: bangun tambang, agent, jurnal Inggris, dan dashboard memakai data simulasi yang jelas dilabeli.
3. Testnet: integrasikan wallet, indeks saldo, perhitungan bobot, vault, dan klaim. Uji transfer antar-wallet, pembelian sesaat, reward kecil, nol peserta, klaim ganda, chain reorg, dan pemulihan server.
4. Gate produksi: dana reward terpisah dari operasional, otorisasi admin multisig, perhitungan dapat diperiksa, event diproses sekali, monitoring, dan review keamanan independen sebelum dana nyata digunakan. Perhitungan off-chain tetap memiliki ketergantungan pada operator; jangan disebut sepenuhnya trustless.

### Dependensi yang Belum Terverifikasi
Halaman Pons yang diperiksa mengonfirmasi launchpad Robinhood Chain, tetapi belum membuktikan dukungan pair GLD maupun aturan creator fee-nya. Situs juga menampilkan pemberitahuan degraded performance. Karena itu, aliran fee GLD dan persentase alokasinya menjadi syarat sebelum integrasi produksi—bukan asumsi.

Pengembangan berikutnya: ekspedisi komunitas, biome baru, dan kosmetik, tanpa mengubah hak pembagian reward.

User additions: “Gld adalah RWA robinhood, untuk minexpx belum launch tokennya, lalu untuk dalamanya jangan pernah tulis demo atau sejenisnya karna memang demo gak perlu di tulis”. References: https://github.com/kodamaMonster/kodama and https://www.antminer.fun/.

## Confirmed scope and user decisions
- Initial phase: persistent mine, agent creation, automatic expeditions, English journal and dashboard. Actual wallet connections and financial claims wait for verified contracts. Unknown financial values use **Not available**; no invented balances or successful claims.
- No in-app demo/simulation/placeholder terminology. Crew bots explicitly identified as CREW BOT, not passed off as holders. Initial statement's simulation-label language is superseded by the later choice.
- “Buat global view walaupum tidak konek, dan tambahkan bot agent nya untuk meraimakan tampilannya”.
- “Model tampilan web buat sebagus mungkin jangan terlalu sama dengan model tampilan kodama, lalu buat animasi menambangnya terlihat hidup tidak kaku tidak berantakan buat elegant dan pro”.
- Rule-engine narration based on real server transitions. No external LLM or keys required.

## Personas
1. Public visitor: watches the live mine and crew before having a wallet or token.
2. Returning explorer: creates a miner, chooses an exploration style, follows the journal and discoveries, pauses/resumes trips.
3. Future MINEPX holder: needs transparent balance-time-weighted funding and claim records, without staking/private-key disclosure.

## Architecture decisions
- Existing React 19 application, TypeScript 4.9.5 (CRA-compatible), PixiJS 8.21.0, React Router, Shadcn/Radix controls, Sonner notifications. Preserve environment-defined external API URL.
- Main routes: `/`, `/agent`, `/rewards`, `/guide`, and friendly unknown-route screen.
- Original generated cave bitmap at `frontend/public/assets/underground.jpg`; original programmatic pixel miner textures in `sprites.ts`. No Kodama sprite or Solana code transplanted.
- FastAPI on configured supervisor port, MongoDB from protected MONGO_URL/DB_NAME. Lifespan-managed asynchronous expedition worker, tick every two seconds. Six phases of 18 seconds; complete cycle 108 seconds.
- Absolute elapsed-time clock persisted in MongoDB. Pausing stores elapsed active time; resuming restarts its clock. Recovery catches up totals/discoveries deterministically and preserves the latest 36 missed transitions. Unique event IDs and optimistic agent revision updates protect retry consistency.
- Collections: `agents`, `events`, `sessions`. Public response models exclude Mongo `_id`, owner, and token hashes. Indexed unique agent ID, sparse unique owner, unique event ID, unique session token hash.
- Current identity is a server-issued anonymous bearer capability, SHA256-hashed in MongoDB, kept in browser localStorage. One agent per browser session. This is NOT wallet authentication or proof of financial eligibility. Clearing browser storage loses current access. One-agent-per-wallet enforcement belongs to the wallet phase.
- Financial module is intentionally nontransactional. `/api/rewards` reports null unknown balances/contracts and no distributions; `/api/rewards/claim` rejects with HTTP409. Wallet CTA opens a truthful readiness notice, not a fake wallet connection.
- No mock API integrations. Game activity is the real server-owned game state, not chain activity. Game ore is not GLD and does not affect reward entitlement.

## Implemented — 2026-09-19
- Public shared mine, original cave artwork and 12 named resident crew bots with personalities and varied route preferences.
- Pixi walking, mining pickaxe swings, ore sparks, refinery embers, loaded ore carts, distinct routes for balanced/deep/careful exploration, label collision avoidance, zoom/reset/fullscreen and independent animation pause. Reduced-motion preference respected.
- Create agent (name, four avatars, three styles), start/pause/resume; server-side progression while browser is closed; persistent counters and discovery thresholds.
- English event journal, personal/global filters, more/less history, individual miner inspection from map or expandable full crew roster.
- Dedicated My Agent page, discovery cabinet (pyrite at 1 expedition, quartz at 3, azurite at 6), Field Guide cycle and expandable FAQs.
- Reward transparency page separates estimated/claimable, documents balance-time formula and exact constraints, funding verification table, empty distribution ledger, operator/jurisdiction notices.
- Responsive charcoal/brass/gold interface, original visual identity, English-only UI, loading/empty/error states, focusable controls and data-test IDs.
- Tested public API, session access isolation, invalid/duplicate creation, start/pause/resume, progression without polling, 108s-cycle discovery, unique journal events and truthful financial blocking: 11/11 backend tests passed.
- Frontend tests exercised all routes/dialogs/filters/controls at 1920×800 and390×844; canvas nonblank and successive frames change. Corrected HTML regex-v name validation, hook dependencies, mobile Sonner resize overflow, long unbroken agent-name layout. Final screenshots show zero right-edge overflow for all routes, including active notifications and 24-character names.
- Final production build succeeds. Testing-only agent records created by main agent and documented agent tests cleaned by exact IDs; unrelated agents retained.

## Verification references
- `test_reports/iteration_1.json`, `test_reports/pytest/pytest_results.xml`, `backend/tests/test_minepx_api.py`.
- Follow-up screenshots: `/app/desktop-refined-world.jpg`, `/app/mobile-refined-world.jpg`, `/app/mobile-long-name-toast.jpg`.
- Build output: `/app/frontend/build-check.log`.
- Current preview: https://minepx-vault.preview.emergentagent.com.
- Research evidence: `memory/INTEGRATION_VERIFICATION.md`.

## Prioritized backlog / next tasks

### P0 — prerequisites before on-chain money
1. Verify official GLD contract, decimals and Stock Token distribution restrictions per jurisdiction; no assumed contract/address.
2. Obtain authoritative Pons pair support, fee recipient/denomination, project share, claim mechanics and graduation changes. Agree pool percentage.
3. Confirm chain ID, RPC/testnet, explorer and supported wallet transports. Implement wagmi/viem ownership proof and wallet linking; prevent duplicate wallet agents and unauthorized links.
4. Implement chain transfer indexer with confirmation depth, reorg rollback, idempotent ingestion, cursor recovery and reconciliation. Wallet selling must preserve prior accrued rights.
5. Implement high-precision balance-time ledger and immutable allocations, fractional carry, no-participant carry, no per-wallet bonus. Scope eligibility start explicitly; do not silently treat guest creation as historic financial activation.
6. Separate-funded Solidity vault, replay-proof claims, multisig administration, audit trail, monitoring, independent security review before real funds.
7. Test wallet transfers, brief purchase/flash holding, tiny fractions, zero participants/income, double claims, duplicate chain events, reorg and crash recovery.

### P1 — game/platform robustness
- Guest access recovery and explicit migration to authenticated wallet ownership.
- Separate worker service/leader coordination for multiple instances; rate limits, metrics, backpressure and journal retention policy.
- Pagination/spatial interest management beyond 250 visible agents; many-agent overlap stress tests.
- More meaningful personality-driven interaction events, progress-triggered stories and a persistent cosmetic inventory (no financial effects).
- Contract verification records and real distribution CSV/export once ledger is implemented.

### P2 — subsequent product enhancements
- Community expeditions, additional biomes, purely cosmetic unlocks.
- Shareable agent discovery cards for community sharing.
- Optional budget-capped server-side English LLM narration only after user approval, retaining deterministic game/financial boundaries and fallback.

## Explicitly not implemented
No token launch, real wallet connection, holding validation, chain ingestion, live fee collection, financial ledger/vault/distribution or GLD claims. No staking, burns, paid boosts, monsters, APY claims or financial influence from game activity. These boundaries follow the user's selected initial phase, not failed integrations.
