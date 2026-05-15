# FoulPlay / poke-engine Champions OU 完全再現 実装計画仕様書

## 0. 絶対条件

本計画の最終目標は、FoulPlay を Pokemon Showdown の `[Gen 9 Champions] OU` で完全再現レベルで動作させることである。

「最低限動く」「主要 mechanics のみ」「MVP」「暫定対応」「未対応 mechanics を警告で握りつぶす」は禁止する。実装順序は分割するが、仕様範囲は分割しない。

対象 format:

- Pokemon Showdown 表示名: `[Gen 9 Champions] OU`
- 内部 format id: `gen9championsou`
- battle type: singles
- 対象外: Champions BSS, Champions VGC, Bo3, Custom Game, Draft

ただし、Champions OU の完全再現に必要な Champions 共通 mechanics は全て実装対象である。

---

## 0.1 開発開始前提条件

本計画に従って開発を開始する前に、必ず以下の状態であることを確認する。以下の条件から外れている場合、Codex は無理に実装を開始してはならない。まず環境差分を報告し、復旧または方針確認を行う。

確認済みの基準状態:

- FoulPlay repository:
  - path: `C:\Users\izure\foul-play`
  - branch state: `main...origin/main`
  - commit: `13db2786b4fdbc742d627e21dd4ee1de6bf963b0`
  - expected untracked entries before implementation: `.codex/`, `docs/`
- poke-engine repository:
  - path: `C:\Users\izure\poke-engine`
  - branch state: `main...origin/main`
  - commit: `c046620c68065862d1f2581e2f76944a95bc2bd7`
  - expected working tree: clean
- Pokemon Showdown repository:
  - path: `C:\Users\izure\pokemon-showdown`
  - branch state: `master...origin/master`
  - commit: `e1290bb1fc267e70d474c6a56e2f4d860bb86cf9`
  - expected working tree: clean
  - required files:
    - `config/formats.ts`
    - `data/mods/champions/abilities.ts`
    - `data/mods/champions/conditions.ts`
    - `data/mods/champions/formats-data.ts`
    - `data/mods/champions/items.ts`
    - `data/mods/champions/learnsets.ts`
    - `data/mods/champions/moves.ts`
    - `data/mods/champions/rulesets.ts`
    - `data/mods/champions/scripts.ts`
- Toolchain:
  - Python: `Python 3.13.13`
  - Rust: `rustc 1.95.0 (59807616e 2026-04-14)`
  - Cargo: `cargo 1.95.0 (f2d3ce0bd 2026-03-21)`
  - pytest: `pytest 9.0.3`
  - ruff: `ruff 0.6.5`
  - installed poke-engine package: `poke-engine 0.0.46`
- Baseline verification:
  - `python -m pytest tests` passes with `524 passed`
  - `python -m ruff check` passes with `All checks passed!`
- Codex execution environment:
  - Windows sandbox mode must allow local commands to run.
  - Known working setting: `[windows] sandbox = "unelevated"`
  - If `CreateProcessWithLogonW failed: 1326` appears, stop and fix the Codex sandbox configuration before proceeding.

Preflight commands:

```powershell
cd C:\Users\izure\foul-play
git status --short --branch
git rev-parse HEAD
python --version
rustc --version
cargo --version
python -m pytest --version
python -m ruff --version
python -m pip show poke-engine

cd C:\Users\izure\poke-engine
git status --short --branch
git rev-parse HEAD

cd C:\Users\izure\pokemon-showdown
git status --short --branch
git rev-parse HEAD
Test-Path C:\Users\izure\pokemon-showdown\config\formats.ts
Test-Path C:\Users\izure\pokemon-showdown\data\mods\champions\scripts.ts
```

Baseline test commands:

```powershell
cd C:\Users\izure\foul-play
python -m pytest tests
python -m ruff check
```

停止条件:

- 上記 commit と異なる repository state で、差分の理由が未確認である。
- FoulPlay / poke-engine / Pokemon Showdown のいずれかの working tree に予期しない変更がある。
- `pytest` または `ruff` が実行できない。
- baseline test が失敗している。
- Pokemon Showdown の Champions mod files が存在しない。
- Codex から `git status --short --branch` または `rg --files` が実行できない。
- installed `poke-engine` と local `C:\Users\izure\poke-engine` の役割が区別されていない。
- `.pytest_cache/` などの cache permission warning が重大な git 操作やテスト実行を妨げている。

上記の停止条件に該当する場合、Codex は実装を開始せず、観測した差分、想定原因、復旧手順を提示すること。

---

## 1. Source of Truth

実装者は最初に upstream commit を固定する。以後、全ての生成物、テスト fixture、差分検証はこの commit を基準にする。

### 1.1 Pokemon Showdown

Primary source:

- Repository: https://github.com/smogon/pokemon-showdown
- 必須参照ファイル:
  - `config/formats.ts`
  - `data/mods/champions/abilities.ts`
  - `data/mods/champions/conditions.ts`
  - `data/mods/champions/formats-data.ts`
  - `data/mods/champions/items.ts`
  - `data/mods/champions/learnsets.ts`
  - `data/mods/champions/moves.ts`
  - `data/mods/champions/rulesets.ts`
  - `data/mods/champions/scripts.ts`
  - `data/moves.ts`
  - `data/items.ts`
  - `data/abilities.ts`
  - `data/pokedex.ts`
  - `data/learnsets.ts`
  - `data/typechart.ts`
  - `data/rulesets.ts`
  - `sim/*` の damage、actions、pokemon、dex 関連実装

確認時点の Champions OU は `config/formats.ts` 上で `mod: 'champions'` を使う singles format である。実装時点で必ず再確認する。

### 1.2 FoulPlay

Primary source:

- Repository: https://github.com/pmariglia/foul-play
- 重要領域:
  - CLI / config: `run.py`, `config.py`
  - mod 適用: `data/mods/apply_mods.py`
  - battle state: `fp/battle.py`, `fp/battle_modifier.py`, `fp/run_battle.py`
  - search integration: `fp/search/*`
  - protocol: `fp/websocket_client.py`
  - data: `data/pokedex.json`, `data/moves.json`, `data/pkmn_sets.py`, `data/mods/*`
  - team loading: `teams/*`
  - constants: `constants.py`

FoulPlay には既に `apply_mods()` が存在する。これは Pokemon Showdown mod を汎用的にロードする仕組みではなく、FoulPlay 内部 JSON / constants を世代別に書き換えるための処理である。

### 1.3 poke-engine

Primary source:

- Repository: https://github.com/pmariglia/poke-engine
- 重要領域:
  - feature 定義: `Cargo.toml`
  - Python binding: `poke-engine-py/*` または repository 内の Python binding package
  - state: `src/state.rs`, `src/engine/state.rs`
  - choices / moves: `src/choices.rs`, move table 定義箇所
  - species / names: `src/pokemon.rs`
  - base stats / formes: `src/engine/base_stats.rs`
  - items: `src/engine/items.rs`
  - abilities: `src/engine/abilities.rs`
  - damage: `src/engine/damage.rs` または damage calculation 実装箇所
  - instruction generation: `src/engine/generate_instructions.rs` または equivalent
  - tests: `tests/*`

poke-engine は runtime mod loader を持たない。Champions は runtime mod としてではなく、`gen9champions` compile-time target として追加する。

---

## 2. 成果物

実装完了時に以下が存在すること。

1. `docs/champions-ou-implementation-plan.md`
   - 本仕様書。
2. `docs/champions-ou-source-lock.md`
   - Pokemon Showdown / FoulPlay / poke-engine の参照 commit SHA。
   - 生成日時。
   - 生成コマンド。
3. Showdown data import scripts
   - pinned Pokemon Showdown commit から Champions data を取得する。
   - FoulPlay 用 data と poke-engine 用 data を生成する。
4. FoulPlay Champions support
   - `gen9championsou` を正式 format として扱う。
   - Champions data mod を適用する。
   - Mega 有効 / Tera 無効を正しく処理する。
5. poke-engine Champions support
   - `gen9champions` feature。
   - Champions stat / PP / damage / condition / item / Mega behavior。
6. Test suites
   - data parity tests。
   - mechanics parity tests。
   - FoulPlay integration tests。
   - poke-engine vs Showdown fixture tests。
   - local Showdown E2E tests。
7. 未対応リスト
   - 完了時点で空でなければならない。
   - 空でない場合は完了扱い禁止。

---

## 3. 実装方針

### 3.1 FoulPlay 側の方針

`apply_mods()` は新規作成しない。既存の `data/mods/apply_mods.py` を拡張する。

実装方針:

- `apply_mods(game_mode)` が `gen9championsou` を検出する。
- `apply_gen_9_champions_mods()` を追加する。
- 通常 `gen9` と Champions を混同しない。
- Champions mod は通常 Gen 9 data をベースに上書きする。
- FoulPlay の内部 data model にない概念は追加する。
- 未表現の Showdown behavior を無視しない。

FoulPlay で追加・変更する概念:

- `pokemon_format == "gen9championsou"` 判定。
- `generation == "gen9"` だが mechanics profile は `champions`。
- `can_terastallize == False` を search/state 両方に反映。
- `can_mega_evo == True` を Showdown request JSON と item/species 条件から反映。
- Champions stat formula による stats。
- Champions PP rules。
- Champions legal item / move / learnset。
- Champions-specific unknown set source。

### 3.2 poke-engine 側の方針

poke-engine には runtime mod loader を追加しない。理由は、既存設計が Rust enum / static table / feature flag に強く依存しており、runtime mod を後付けすると全域の型安全性と探索性能を壊すためである。

実装方針:

- `Cargo.toml` に `gen9champions` feature を追加する。
- `gen9champions` は Gen 9 をベースにしつつ Champions 差分を compile-time で有効化する。
- `gen9champions` と通常 `gen9` は同時に有効化しない。
- 同時有効化時は compile error または build script error にする。
- Python binding から `gen9champions` build を選択できるようにする。

禁止:

- `gen9` feature の中へ Champions logic を条件なしで混ぜること。
- FoulPlay 側だけで補正し、poke-engine 側を通常 Gen 9 のまま使うこと。
- `gen9championsou` 起動時に通常 `gen9` engine を黙って使うこと。

---

## 4. Champions OU 仕様差分

以下は Pokemon Showdown の `data/mods/champions/*` を source of truth として実装する。実装時点で upstream を確認し、ここにない差分があればこの仕様書を更新してから実装する。

### 4.1 Format

Showdown format:

```ts
name: "[Gen 9 Champions] OU"
mod: "champions"
ruleset: ["Standard"]
banlist: ["AG", "Uber", "Moody", "Baton Pass", "Last Respects", "Shed Tail"]
```

実装要件:

- `gen9championsou` で ladder/challenge/accept/search が可能。
- FoulPlay の team loader は `teams/teams/gen9championsou` を参照する。
- `--team-name` 未指定時の default は `gen9championsou`。
- random battle 判定に誤って入らない。
- `requires_team()` は true を返す。

### 4.2 Stat Formula

Champions stat formula:

- HP: `base + ev + 75`
- Attack / Defense / SpA / SpD / Speed: `base + ev + 20`
- nature 補正は non-HP にのみ適用。
- Showdown と同じ truncation を使う。

FoulPlay 対応:

- `fp.helpers.calculate_stats` または equivalent に mechanics profile を渡せるようにする。
- 通常 Gen 9 と Champions の stat formula を分離する。
- request JSON で得られる自分側 stats は Showdown を source of truth とする。
- unknown opponent stats 推定は Champions formula を使う。

poke-engine 対応:

- base stats から actual stats を作る箇所を `gen9champions` で分岐する。
- state deserialize 時に既に actual stats が渡る場合は二重補正しない。
- stat boost 後の値は通常ルールと同じ boost multiplier を使う。

テスト:

- nature neutral / plus / minus。
- ev 0 / 1 / 32 / 252 相当。
- HP と non-HP の両方。
- Mega 前後の base stat 変更後。
- FoulPlay 推定値と Showdown `/dt` または battle fixture の値が一致。

### 4.3 PP Rules

Champions PP rules:

- base PP が 20 を超える move は 20 に制限。
- `calculatePP(move, ppUps)` は Showdown Champions と一致。

FoulPlay 対応:

- `data/moves.json` へ Champions PP cap を適用。
- request JSON 由来の current PP を優先。
- unknown opponent move PP 推定時に Champions PP を使う。

poke-engine 対応:

- move table の max PP を Champions で上書き。
- instruction generation の `DecrementPP` が Champions PP を前提にする。
- Disabled move 判定と PP 0 判定が通常 Gen 9 と混線しない。

テスト:

- Recover 系など base PP 5/10/16/20/32/40 の代表技。
- PP Ups あり/なし。
- FoulPlay request JSON からの PP と engine state の PP が一致。

### 4.4 Terastallization

Champions では Tera 使用不可。

FoulPlay 対応:

- Showdown request JSON に `canTerastallize` が存在しても Champions profile では無効扱い。
- search candidate に `terastallize` action を含めない。
- battle log に Tera 関連 event が来た場合は error として扱う。黙って無視しない。

poke-engine 対応:

- `gen9champions` では Tera option を生成しない。
- Tera type による STAB / defensive type override を発生させない。
- state serializer に Tera field が存在する場合は Champions では none を要求する。

テスト:

- `canTerastallize: true` を含む異常 fixture で FoulPlay が Tera action を生成しない。
- engine legal choices に Tera が存在しない。
- Tera state を deserialize しようとした場合の扱いを明示する。

### 4.5 Mega Evolution

Champions では Mega Evolution が有効。

FoulPlay 対応:

- `Battle.mega_evolve_possible()` が `gen9championsou` で true になる。
- Mega Stone held item から `canMegaEvo` を扱う。
- Showdown request JSON の `canMegaEvo` を優先する。
- Mega 後の species / ability / base stats / item lock を state に反映する。
- faint 後に Mega forme が revert しない Champions behavior を反映する。
- `smart_team_preview` に必要な Champions 固有 form ambiguity があれば追加する。

poke-engine 対応:

- Mega Stone data を Champions legal item として持つ。
- species -> mega species mapping を持つ。
- Mega action を legal choice として生成する。
- Mega action と move action の同時指定を表現する。
- Mega 後の ability / type / base stats / weight / forme を state に適用する。
- faint 後に base forme へ戻さない。
- Mega Rayquaza 相当の required move 条件が Showdown と一致する。

テスト:

- 通常 Mega Stone。
- Mega Rayquaza required move。
- Mega 不可能な item。
- Mega 済みの再 Mega 禁止。
- faint 後の forme 維持。
- Illusion など見た目に関係する protocol は Showdown fixture で確認。

### 4.6 Damage

Showdown Champions の damage flow を再現する。

対象:

- base damage。
- spread modifier は OU singles では基本不要だが、engine 共通処理として Showdown と矛盾しないようにする。
- Parental Bond modifier。
- weather modifier。
- crit。
- random factor。
- STAB。
- Stellar/Tera 関連は Champions では無効。
- type effectiveness。
- burn physical damage half。
- final modifier。
- minimum damage。
- 16-bit truncation。

FoulPlay 対応:

- FoulPlay 側の簡易 damage / speed 推定がある場合は Champions profile を適用。
- 最終的な search 評価は poke-engine の damage を source of truth とする。

poke-engine 対応:

- `gen9champions` damage calculation を Showdown Champions と一致させる。
- type effectiveness clamp を Showdown と一致。
- weather damage modifier を conditions と連動。
- item / ability / move modifiers を通常 Gen 9 から漏れなく継承し、Champions 差分で上書き。

テスト:

- neutral / resisted / super effective / 4x / 0.25x。
- STAB あり/なし。
- burn physical。
- crit。
- weather Fire/Water/Hydro Steam。
- Life Orb 等 final modifier。
- multi-hit。
- fixed damage / status move / immune target。
- Showdown fixture と damage roll 配列が完全一致。

### 4.7 Conditions / Status / Weather

Showdown `conditions.ts` を source of truth とする。

実装対象:

- paralysis:
  - 行動不能率。
  - speed 低下との関係。
- sleep:
  - turn distribution。
  - ability / move 由来表示は意思決定に不要だが state transition は必要。
- freeze:
  - fixed turn / thaw probability。
  - defrost move。
- rain / primordial sea:
  - Water boost。
  - Fire suppress。
- sun / desolate land:
  - Fire boost。
  - Water suppress。
  - Hydro Steam exception。
- sandstorm:
  - Rock type SpD boost。
- snowscape:
  - Ice type Def boost。
- Trick Room:
  - action speed underflow 修正。

FoulPlay 対応:

- `Battle.get_effective_speed()` を Champions profile 対応にする。
- weather name / field state / remaining turns の protocol parsing を既存 Gen 9 と比較して不足がないか確認する。

poke-engine 対応:

- status turn counters を Champions に合わせる。
- weather damage modifiers を damage pipeline へ組み込む。
- stat modification phase に sand/snow boosts を入れる。
- Trick Room order を Showdown と一致させる。

テスト:

- paralysis 行動不能 probability。
- sleep 2/3 turn distribution。
- freeze thaw。
- weather modifier 全組み合わせ。
- sand/snow defensive stat。
- Trick Room 低速/高速/同速。

### 4.8 Items

Showdown `items.ts` を source of truth とする。

対応:

- Champions で legal になる Mega Stones。
- Champions で Past / nonstandard になる item。
- battle outcome に影響する item script。
- White Herb の Champions 固有 queue behavior。
- Choice items 等、通常 Gen 9 から継承される item。

FoulPlay 対応:

- item legality / item inference / unknown item handling に Champions item data を適用。
- `constants.CHOICE_ITEMS` 等の item group が Champions と矛盾しないか確認する。

poke-engine 対応:

- `Items` enum に不足 item があれば追加。
- item parser が Showdown id と一致する。
- item before move / after move / modify damage / modify stat hooks を Champions と一致させる。

テスト:

- Mega Stone。
- Choice item。
- White Herb。
- weather rock 系が legal/illegal どちらかを Showdown と一致。
- nonstandard item を含む team validation。

### 4.9 Moves / Learnsets / Abilities / Species

Showdown Champions mod は Gen 9 base data を継承し、一部を上書きする。

FoulPlay 対応:

- `moves.json` へ Champions move overrides を適用。
- `pokedex.json` へ Champions species/form overrides を適用。
- `pkmn_sets.py` または equivalent の unknown set source に Champions 用 namespace を追加。
- learnset legality を team fixture validation で確認する。

poke-engine 対応:

- move enum / parser / data table に Champions で必要な move を全て持たせる。
- species enum / parser / base stats に Champions で必要な species / formes / mega formes を全て持たせる。
- ability enum / parser / hooks に Champions で必要な ability を全て持たせる。
- Showdown id normalization と engine id normalization を一致させる。

テスト:

- Champions legal species 全件 parse。
- Champions legal moves 全件 parse。
- Champions legal items 全件 parse。
- Mega formes 全件 parse。
- FoulPlay team paste -> packed team -> Showdown validation -> FoulPlay internal team -> poke-engine state まで往復。

---

## 5. 作業手順

### Phase 1: Repository baseline

実行すること:

1. `git status --short --branch`
2. `rg --files`
3. `python --version`
4. `rustc --version`
5. `cargo --version`
6. FoulPlay test suite 実行。
7. poke-engine test suite 実行。
8. 現在の dependency lock 確認。

記録すること:

- FoulPlay commit。
- poke-engine dependency version。
- Python version。
- Rust version。
- baseline test result。
- 既存 failure がある場合は、Champions 実装由来 failure と混同しないように記録。

完了条件:

- 変更前 baseline が記録済み。
- local repository の構造が把握済み。
- 既存 failure が分類済み。

### Phase 2: Showdown source lock

実行すること:

1. Pokemon Showdown を別 directory または cache に clone。
2. `git rev-parse HEAD` を記録。
3. `config/formats.ts` から `[Gen 9 Champions] OU` を抽出。
4. `data/mods/champions` の全ファイル hash を記録。
5. `data/moves.ts`, `data/items.ts`, `data/abilities.ts`, `data/pokedex.ts`, `data/learnsets.ts` の hash を記録。

生成すること:

- `docs/champions-ou-source-lock.md`
- `generated/showdown/champions-source-manifest.json`

manifest fields:

```json
{
  "pokemon_showdown_commit": "...",
  "format_id": "gen9championsou",
  "format_name": "[Gen 9 Champions] OU",
  "source_files": {
    "config/formats.ts": "sha256:...",
    "data/mods/champions/scripts.ts": "sha256:..."
  }
}
```

完了条件:

- source lock が存在する。
- source lock なしでは generation script が失敗する。

### Phase 3: Data extraction / generation

実装すること:

- Showdown TypeScript data を読み取る extraction script。
- script は直接 regex だけに依存しない。
- 可能なら Pokemon Showdown の Dex を Node.js で起動し、resolved mod data を JSON として吐く。
- resolved data は `Dex.mod('champions')` 相当から取得する。
- 取得できない script behavior は `manual_mechanics` として manifest に出す。

生成物:

- FoulPlay 用:
  - `data/mods/gen9_champions_move_mods.json`
  - `data/mods/gen9_champions_pokedex_mods.json`
  - `data/mods/gen9_champions_item_mods.json`
  - `data/mods/gen9_champions_learnsets.json`
  - `data/mods/gen9_champions_format.json`
- poke-engine 用:
  - `generated/poke_engine/champions_moves.rs`
  - `generated/poke_engine/champions_items.rs`
  - `generated/poke_engine/champions_species.rs`
  - `generated/poke_engine/champions_abilities.rs`
  - `generated/poke_engine/champions_learnsets.rs`
  - exact destination は既存 module 構成に合わせる。

data generation tests:

- 同一 Showdown commit から同一 output。
- output に timestamp を含めない。
- 全 move / item / species id が normalized。
- Showdown id と FoulPlay id と poke-engine id の mapping table を生成する。
- mapping 不能 id が 0 件。

完了条件:

- 生成物が deterministic。
- unsupported / unmapped / manual behavior list が出る。
- unmapped id が 0 件になるまで完了扱いしない。

### Phase 4: FoulPlay implementation

変更対象:

- `config.py`
- `run.py`
- `data/mods/apply_mods.py`
- `fp/battle.py`
- `fp/battle_modifier.py`
- `fp/search/*`
- `fp/helpers.py`
- `constants.py`
- `teams/*`
- tests directory

実装詳細:

1. Format profile を追加する。
   - `gen9championsou`
   - generation: 9
   - mechanics_profile: `champions`
   - requires_team: true
   - tera_allowed: false
   - mega_allowed: true

2. `apply_mods()` 拡張。
   - `if "gen9champions" in game_mode` を通常 `gen9` 判定より先に処理する。
   - `apply_gen_9_champions_mods()` を追加。
   - base Gen 9 data を保持した上で Champions overrides を適用。
   - `all_move_json` / `pokedex` / item data / learnsets を mutation する場合は既存の mutation check と整合させる。

3. Stat calculation。
   - `calculate_stats(..., mechanics_profile="standard")` 形式へ拡張。
   - Champions では `base + ev + 75/20` formula。
   - request JSON 由来 stats を二重計算しない。

4. Mega/Tera action handling。
   - Champions では Tera candidate を生成しない。
   - `mega_evolve_possible()` が `gen9championsou` で true。
   - request JSON の `canMegaEvo` を move choice construction に反映。
   - Mega 後 species update を battle log parser で確認。

5. Team handling。
   - `teams/teams/gen9championsou/` を追加。
   - 少なくとも Mega Stone 使用 team、非 Mega team、banlist 違反検出用 fixture を用意。
   - Showdown validate に通る team のみ positive fixture にする。

6. Unknown sets。
   - Champions usage stats が存在しない場合でも通常 Gen 9 OU stats を黙って流用しない。
   - Champions 用 set source を明示する。
   - set source が不足する species は conservative unknown set を生成し、未確認として log する。
   - ただし mechanics 完全再現とは別に、set 推定の精度は gameplay strength の問題として分類する。

FoulPlay tests:

- `gen9championsou` config parse。
- `requires_team()` true。
- `apply_mods("gen9championsou")` 後の PP cap。
- Champions stat formula。
- Tera choice absent。
- Mega choice present when legal。
- Mega choice absent when illegal。
- team load success。
- Showdown packed team upload payload。
- normal `gen9ou` regression。

完了条件:

- FoulPlay が Champions OU を通常 Gen 9 OU と別 profile として扱う。
- FoulPlay が Tera を出さない。
- FoulPlay が Mega を条件付きで出す。
- FoulPlay internal data が generated Champions data と一致。

### Phase 5: poke-engine implementation

変更対象:

- `Cargo.toml`
- build scripts if present
- `src/*` engine modules
- `poke-engine-py/*`
- `tests/*`

実装詳細:

1. Feature。
   - `gen9champions` を追加。
   - `gen9champions` は `gen9` 相当 data を内包するが、通常 `gen9` feature と同時指定は禁止。
   - compile-time guard を追加。

2. Data。
   - generated Champions Rust data を engine module に組み込む。
   - enum に不足 id があれば追加。
   - parser は Showdown id normalization と一致。
   - unknown id は panic ではなく parse error として tests で検出可能にする。ただし runtime battle 中に握りつぶさない。

3. State。
   - state に mechanics profile を持たせるか、feature で完全分離する。
   - serializer / deserializer が Champions state を表現。
   - Tera fields は Champions で none。
   - Mega state は species/form/item/action として表現。
   - faint 後 Mega non-revert を state transition に反映。

4. Choices。
   - legal choices に Mega+Move を含める。
   - legal choices に Tera を含めない。
   - disabled move / PP / choice lock / assault vest / taunt / encore 等の既存制約を維持。

5. Stat / Speed。
   - Champions stat formula。
   - nature truncation。
   - sand/snow defensive stat。
   - Trick Room speed ordering。

6. Damage。
   - Showdown Champions damage order と一致。
   - weather / crit / random / STAB / type effectiveness / burn / final modifier / min damage。
   - Tera/Stellar branches は Champions では inactive。
   - Mega stats / abilities を damage に反映。

7. Conditions。
   - paralysis / sleep / freeze。
   - rain / sun / sand / snow / primordial / desolate。
   - status counters。
   - probability distribution。

8. Items / Abilities / Moves。
   - Mega Stones。
   - White Herb。
   - Choice items。
   - weather rocks 等 legal/illegal and behavior。
   - ability hooks を Showdown と一致。

9. Python binding。
   - `pip install` / `maturin` / existing build flow で `gen9champions` を指定可能。
   - FoulPlay から import した engine が Champions build か判定できる API を追加。
   - 例: `poke_engine.get_build_profile() == "gen9champions"`。

poke-engine tests:

- compile `gen9champions`。
- compile normal `gen9`。
- reject simultaneous `gen9` + `gen9champions`。
- stat formula parity。
- PP parity。
- legal choices parity。
- damage roll parity。
- condition transition parity。
- Mega transition parity。
- Tera absent。
- serialization round trip。
- Python binding profile check。

完了条件:

- `gen9champions` engine が単体で Showdown fixtures と一致。
- normal `gen9` regression が壊れていない。
- Python binding が build profile を返せる。

### Phase 6: FoulPlay / poke-engine integration

実装すること:

1. install/build command。
   - `make poke_engine GEN=gen9champions` または既存流儀に合わせた同等コマンド。
   - README / docs に明示。
   - 通常 `gen9` と Champions を取り違えない名前にする。

2. startup guard。
   - FoulPlay 起動時、`pokemon_format == "gen9championsou"` なら engine profile が `gen9champions` であることを確認。
   - 不一致なら即 error。
   - warning で続行は禁止。

3. state bridge。
   - FoulPlay Battle -> poke-engine State serialization に Champions 固有情報を含める。
   - Mega availability。
   - current forme。
   - item。
   - PP。
   - weather/status counters。
   - Tera none。
   - stat formula で算出済み stats か base+EV 入力かを明確化。

4. decision bridge。
   - poke-engine choice -> Showdown command 変換。
   - Mega+Move command。
   - switch command。
   - no Tera command。
   - illegal command 生成時は fail fast。

Integration tests:

- FoulPlay startup with Champions engine succeeds。
- FoulPlay startup with normal Gen 9 engine fails。
- Mega+Move command string。
- Tera command absent。
- Showdown request fixture -> engine state -> best move -> Showdown command。
- battle log update -> next state consistency。

完了条件:

- engine mismatch が検出される。
- search result が Showdown legal command のみ。
- state bridge に欠落 field がない。

### Phase 7: Showdown parity fixture suite

fixture の作り方:

- pinned Pokemon Showdown を local で起動。
- deterministic battle scripts を作る。
- 各 fixture は以下を保存する。
  - initial Showdown state。
  - public battle log。
  - request JSON。
  - chosen moves。
  - Showdown outcome。
  - expected engine state transition。
  - expected probabilities。
  - expected damage rolls。

fixture categories:

1. Stat / speed
2. PP
3. Mega
4. Tera absence
5. Damage
6. Status
7. Weather
8. Items
9. Abilities
10. Switching / hazards
11. Faint / forme persistence
12. Team preview
13. Illegal team / banlist
14. Long battle regression

比較基準:

- deterministic outcome は完全一致。
- random outcome は probability distribution が一致。
- damage rolls は配列一致。
- legal choices は集合一致。
- battle command は Showdown validate に通る。
- divergence が発生した fixture は skip 禁止。原因分類して修正する。

完了条件:

- 全 fixture が合格。
- skip / xfail が 0。
- unknown / TODO が 0。

### Phase 8: E2E

E2E scenario:

1. local Pokemon Showdown を pinned commit で起動。
2. FoulPlay を `--pokemon-format gen9championsou` で起動。
3. challenge_user / accept_challenge の両方を確認。
4. Champions OU legal team を upload。
5. team preview。
6. Mega 可能 turn。
7. status/weather/item を含む turn。
8. battle end。
9. replay / battle log / FoulPlay internal state dump を保存。
10. turn ごとに Showdown state と FoulPlay/poke-engine state を比較。

合格条件:

- protocol desync なし。
- illegal choice なし。
- exception なし。
- Mega command 正常。
- Tera command なし。
- state divergence なし。
- battle end まで完走。

注意:

- 1 試合完走だけでは完了条件にならない。
- E2E は mechanics fixture suite 合格後の統合確認である。

---

## 6. 完全再現チェックリスト

完了時に全て yes であること。

- [ ] Pokemon Showdown commit が固定されている。
- [ ] Champions OU format 定義が記録されている。
- [ ] Champions mod files が全て source lock されている。
- [ ] Showdown data generation が deterministic。
- [ ] unmapped species が 0。
- [ ] unmapped moves が 0。
- [ ] unmapped items が 0。
- [ ] unmapped abilities が 0。
- [ ] manual mechanics 未実装が 0。
- [ ] FoulPlay が `gen9championsou` を認識する。
- [ ] FoulPlay が Champions data mod を適用する。
- [ ] FoulPlay が Tera を生成しない。
- [ ] FoulPlay が Mega を生成する。
- [ ] poke-engine `gen9champions` が build できる。
- [ ] normal `gen9` と `gen9champions` が混線しない。
- [ ] engine profile mismatch で起動失敗する。
- [ ] stat formula が Showdown と一致。
- [ ] PP が Showdown と一致。
- [ ] damage rolls が Showdown と一致。
- [ ] speed order が Showdown と一致。
- [ ] status transitions が Showdown と一致。
- [ ] weather behavior が Showdown と一致。
- [ ] item behavior が Showdown と一致。
- [ ] Mega transition が Showdown と一致。
- [ ] faint 後 Mega non-revert が一致。
- [ ] Tera absence が一致。
- [ ] legal choices が Showdown と一致。
- [ ] FoulPlay command が Showdown legal。
- [ ] E2E で protocol desync がない。
- [ ] regression tests が合格。
- [ ] skip / xfail / TODO が 0。
- [ ] 未対応リストが空。

---

## 7. 失敗時の扱い

失敗は終了理由にしない。以下に分類して修正する。

分類:

- data extraction failure
- id normalization failure
- FoulPlay state parsing failure
- poke-engine state representation failure
- mechanics mismatch
- probability mismatch
- damage mismatch
- legal choice mismatch
- Showdown protocol mismatch
- regression failure

各 failure で記録すること:

```text
Failure ID:
Fixture:
Observed:
Expected:
Source of truth:
Suspected layer:
Fix target:
Regression risk:
New test:
Status:
```

修正後、同じ fixture と関連 regression を再実行する。

---

## 8. 完了条件

本計画は以下を全て満たした時だけ完了とする。

1. FoulPlay が `gen9championsou` で起動できる。
2. FoulPlay が Champions OU legal team を扱える。
3. FoulPlay が Champions mechanics profile を使う。
4. poke-engine が `gen9champions` target として build できる。
5. FoulPlay と poke-engine の profile mismatch が検出される。
6. Pokemon Showdown pinned commit と data / mechanics が一致する。
7. 全 parity fixture が合格する。
8. E2E で protocol desync がない。
9. 通常 supported formats の regression が合格する。
10. 未実装、未検証、仕様不明、skip、xfail、TODO が 0。

以上を満たさない場合、実装は未完了である。
