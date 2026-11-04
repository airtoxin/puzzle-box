# ドキュメント

Puzzle Box は、ルールを制約として記述し、回答とヒントの意味を固定したレシピから
一意なパズルを生成する Python ライブラリです。導入は[ルートの README](../README.md)を参照してください。

## 作る・解く・調べる

| 目的 | 文書 |
| --- | --- |
| ルールを画面で選び、UI を合成して生成・表示する | [ローカル Web アプリ](web-app.md) |
| 黒白ルールを選んで生成する | [黒白の合成](composable-shading.md) |
| 部屋の配置・個数・連結・対称を組み合わせる | [固定部屋のルール断片](room-fragments.md) |
| 連結成分の長方形・長方形以外を組み合わせる | [成分の形の断片](component-shapes.md) |
| 数字と部屋を重ねて黒白を生成する | [固定数字の断片](number-fragments.md) |
| 数字から見える白マス数を固定する | [黒どこの可視数](white-visibility.md) |
| 黒・白の各成分から外枠へ到達させる | [成分と外枠の接続](component-border.md) |
| 数字ごとに白い島の面積を指定する | [ぬりかべの島](white-island-areas.md) |
| 数字なしの白成分も許して面積を指定する | [モチコロ型の面積ヒント](white-area-clues.md) |
| 0と数字なしを区別して隣接黒数を指定する | [マインスイーパーの隣接黒数](adjacent-black-counts.md) |
| 隣接する異なる黒成分の面積を合計する | [クロットの黒成分合計](black-component-sum.md) |
| 同色の隣接数・端点・連結を合わせて道にする | [セルの道の断片](cell-path-fragments.md) |
| 部屋の単色と同色の輪なしを組み合わせる | [部屋の単色と森](room-uniform-forest.md) |
| 長方形成分などを辺・角でつなぐ | [8近傍の連結](corner-connected-color.md) |
| 同色の連続する長さを制限する | [連続長の上限](run-length.md) |
| 黒・白の各連結成分を同じサイズにする | [固定成分サイズ](component-size.md) |
| LITS の部屋ピースの同形接触を禁止する | [テトロミノの接触](tetromino-contact.md) |
| セルと行・列の黒数ヒントを混ぜる | [複数のヒント形式](mixed-shading-clues.md) |
| 保存問題を表示し、完成した解答を確認する | [端末で遊ぶ](play-shading.md) |
| 保存JSONの形式・読込エラー・互換性を確認する | [保存問題ファイル](saved-puzzle-files.md) |
| 限定した推論の根拠と、未解決で止まる箇所を確認する | [黒白の推論説明](shading-deductions.md) |
| 生成した複数候補の推論による進み方を比較する | [黒白候補の推論比較](shading-deduction-comparison.md) |
| ルールの矛盾・ヒント不足・seedによる多様性を調べる | [小盤面診断](shading-diagnostics.md) |
| ルールの部分集合・冗長性を比較する | [黒白の組合せ探索](shading-exploration.md) |
| 選んだレシピを保存し、生成へ渡す | [レシピの保存と読込](shading-recipe-files.md) |
| 固定レシピを時間予算付きで生成・検証して測る | [生成ベンチマーク](generation-benchmark.md) |
| 実際に残ったヒントでルールの必要性を調べる | [黒白の保存ヒント診断](stored-clue-rule-diagnostics.md) |
| 辺を回答とするパズルを生成する | [Slitherlink](slitherlink-composition.md) |
| 黒セルとループを接続して生成する | [ヤジリン](yajilin-composition.md) |
| 黒セルと辺の規則・ヒント形式を小盤面で比較する | [異種合成の探索](coupled-rule-exploration.md) |
| 全候補ヒントと削減後のヒントの違いを再現する | [異種合成の固定ヒント比較](coupled-clue-contribution.md) |

例えば、黒白の選定から生成・表示・検証・診断までは次の順に試せます。
`chosen.json` は設定、`puzzle.json` は問題と答え、診断の出力は比較レポートです。
ファイルを使うコマンドは、そのファイルを作るコマンドの成功後に実行してください。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/explore_shading.py --rows 3 --cols 3 --black-counts 3 --candidates count non-touching --hints cell row-count column-count --explain 1 2 --export-recipe chosen.json
uv run --no-sync python examples/generate_shading.py generate --recipe chosen.json --seed 6 --output puzzle.json --quiet
uv run --no-sync python examples/generate_shading.py show puzzle.json
uv run --no-sync python examples/generate_shading.py verify puzzle.json
uv run --no-sync python examples/diagnose_shading_rules.py puzzle.json
```

`show` はヒントだけを表示します。探索・診断には答えや別解が含まれ、保存JSON自体にも答えが入っています。
唯一解とヒントの既約性は、人間の難易度・最少ヒント数・均一抽選を保証しません。
CLIの盤面・試行数の制限や、再現性の範囲は各機能の文書に記載しています。

## 定義を拡張する

| 契約・設計 | 文書 |
| --- | --- |
| パッケージ構成とDSL | [アーキテクチャ](../ARCHITECTURE.md) |
| ルール・空間・回答・ヒントの接続 | [合成の設計](composition-design.md) |
| 独自の黒白ルールを追加し、DSL条件を正しく組み合わせる | [独自ルールの作り方](custom-rules.md) |
| 完成解の抽出とヒント削減の前提 | [生成レシピの契約](generation.md) |
| 既存レシピへ共通の追加制約を適用する | [制約部品の合成](recipe-constraint-composition.md) |
| 既知の個数・連結部品を保存して再構築する | [合成レシピの保存](composed-recipe-files.md) |
| 自作部品を信頼するPythonコードで登録する | [部品の明示登録](custom-component-registration.md) |
| 回答の射影、唯一性、`one_of`、空のループ | [求解の意味](solver-semantics.md) |
| 式と変数を同じモデルに所属させる | [モデル所属](model-ownership.md) |
| 求解後の値とスナップショット | [解から値を読む](solution-values.md) |
| 二部グラフの候補・次数・不正入力 | [マッチングの入力契約](matching-inputs.md) |

## 文書を更新する場所

このディレクトリには、実装の仕様、利用手順、入力契約、制約、設計判断、再実行できる例を置きます。
仕様が変わるときは、対応する文書と例も更新してください。
PRの進捗・ブランチ依存・採用順・特定headのCI結果・作業計画は、対応するPRまたはissueへ記録します。
再現例に必要な環境条件と、日々の検証結果や採用状況は区別します。
