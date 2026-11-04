# ドキュメント

Puzzle Box は、ルールを制約として記述し、回答とヒントの意味を固定したレシピから
一意なパズルを生成する Python ライブラリです。導入は[ルートの README](../README.md)を参照してください。

## 作る・解く・調べる

| 目的 | 文書 |
| --- | --- |
| 黒白ルールを選んで生成する | [黒白の合成](composable-shading.md) |
| セルと行・列の黒数ヒントを混ぜる | [複数のヒント形式](mixed-shading-clues.md) |
| 保存問題を表示し、完成した解答を確認する | [端末で遊ぶ](play-shading.md) |
| 限定した推論の根拠と、未解決で止まる箇所を確認する | [黒白の推論説明](shading-deductions.md) |
| ルールの矛盾・ヒント不足・seedによる多様性を調べる | [小盤面診断](shading-diagnostics.md) |
| ルールの部分集合・冗長性を比較する | [黒白の組合せ探索](shading-exploration.md) |
| 選んだレシピを保存し、生成へ渡す | [レシピの保存と読込](shading-recipe-files.md) |
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
| 完成解の抽出とヒント削減の前提 | [生成レシピの契約](generation.md) |
| 回答の射影、唯一性、`one_of`、空のループ | [求解の意味](solver-semantics.md) |
| 式と変数を同じモデルに所属させる | [モデル所属](model-ownership.md) |
| 求解後の値とスナップショット | [解から値を読む](solution-values.md) |
| 二部グラフの候補・次数・不正入力 | [マッチングの入力契約](matching-inputs.md) |

## 文書を更新する場所

このディレクトリには、実装の仕様、利用手順、入力契約、制約、設計判断、再実行できる例を置きます。
仕様が変わるときは、対応する文書と例も更新してください。
PRの進捗・ブランチ依存・採用順・特定headのCI結果・作業計画は、対応するPRまたはissueへ記録します。
再現例に必要な環境条件と、日々の検証結果や採用状況は区別します。
