# 生成後の問題を比べて、ルールが働く例を選ぶ

`examples/compare_shading_seeds.py` は、保存した黒白レシピから複数の問題を生成し、
**削減後のヒントを固定して、各ルールが唯一解に必要か**を比較します。
同じレシピでも、選ばれた完成解と残るヒントによってルールの役割が変わります。
ルールを増やしたことや生成に成功したことだけでは、全ルールが問題で必要とは限りません。

## ３つのレシピを試す

リポジトリのルートで `uv sync --all-packages --group dev --locked` を実行してから使います。
いずれも既存の４種類の黒白ルールと、セル・行・列のヒントを組み合わせた例です。

| レシピ | 組合せ | 完成解数 / 全候補ヒントで識別できる解数 | 比較する点 |
|---|---|---:|---|
| [diagonal-cells](../examples/recipes/shading-diagonal-cells.json) | 2×2、黒２個＋縦横の黒隣接禁止、セル・行・列ヒント | 2 / 2 | 行列ヒントだけでは対角２解を区別できず、セルヒントが必要 |
| [row-counts](../examples/recipes/shading-row-counts.json) | 2×3、黒３個＋白連結、行ヒント | 10 / 2 | 識別できる２解から生成できても、残った問題では白連結が冗長になる |
| [three-rules](../examples/recipes/shading-three-rules.json) | 3×3、黒３個＋黒隣接禁止＋白だけの2×2禁止、セル・行・列ヒント | 18 / 18 | 同じルール群でも、残るヒントによって各ルールの必要性が変わる |

```sh
uv run --no-sync python examples/compare_shading_seeds.py examples/recipes/shading-diagonal-cells.json --seeds 0 1 2
uv run --no-sync python examples/compare_shading_seeds.py examples/recipes/shading-row-counts.json --seeds 0 1 2
uv run --no-sync python examples/compare_shading_seeds.py examples/recipes/shading-three-rules.json --seeds 0 1 2
```

出力は seed、完成解の識別番号、残ったヒント数、必要なルール番号、個別には冗長なルール番号です。
番号はレシピのルール順で１始まりです。`-` は該当なし、ルールが空なら両方 `-` です。
完成解の番号はその実行内だけで有効で、回転・反転を同一視しません。同じ解でもヒントが違う場合があります。
通常のテキスト表示には完成解や反例を出しません。`--json` には両方を含みます。

three-rules の seed 0 と 1 では、次の違いを再現できます。

```text
Seed | Answer ID | Clues | Necessary rules / Individually redundant rules (remaining clues)
0 | 1 | 4 | - / 1+2+3
1 | 2 | 3 | 1+2+3 / -
```

seed 0 ではどのルールも**１つだけなら**外せます。seed 1 では黒個数・黒隣接禁止・白2×2禁止を
それぞれ外すと、同じ残存ヒントで解数が 2・2・4 に増えます。全セルの候補ヒントを残した場合は
どのルールを外しても１解なので、探索時の「全候補ヒントで冗長」と生成後の必要性は区別してください。
これらの seed の例は Python 3.12 / OR-Tools 9.15 系の実行例です。再現には依存を固定した環境を使います。

## 選んだ問題を保存して解く

比較に含めた seed を明示して、既存の `shading-v1` / `shading-v2` 形式で保存できます。
ファイルの中に正解が入るため、解く際は `show` を使います。

```sh
uv run --no-sync python examples/compare_shading_seeds.py examples/recipes/shading-three-rules.json --seeds 0 1 --export-seed 1 --export-puzzle selected.json
uv run --no-sync python examples/generate_shading.py show selected.json
uv run --no-sync python examples/generate_shading.py verify selected.json
```

表示された `?` のテンプレートを黒 `#` と白 `.` で埋め、
`generate_shading.py check selected.json --answer "各行を/で区切った完成入力"` に渡します。
[黒白の解答確認](play-shading.md)に入力形式があります。
詳しい反例を見たい場合は `diagnose_shading_rules.py selected.json` で確認できます。

エクスポートは新規ファイルだけを作り、既存ファイル・入力レシピを上書きしません。
`--export-seed` と `--export-puzzle` は両方必要で、seed は `--seeds` の中から選びます。
全候補を生成・検証してから書き出します。途中の検証が失敗した場合、問題ファイルを作りません。
ディスク書き込み自体の失敗に対する原子的な保存は保証しません。

## 自分で選んだ組合せへつなぐ

[ルール部分集合の探索](shading-exploration.md)から出力したレシピも使えます。
次の例は、黒２個と黒隣接禁止に行列ヒントだけを指定しています。

```sh
uv run --no-sync python examples/explore_shading.py --rows 2 --cols 2 --candidates count non-touching connected-white --black-counts 2 --hints row-count column-count --explain 1 2 --export-recipe ambiguous.json
uv run --no-sync python examples/compare_shading_seeds.py ambiguous.json
uv run --no-sync python examples/explore_shading.py --rows 2 --cols 2 --candidates count non-touching connected-white --black-counts 2 --hints row-count column-count --explain 1 2 3 --export-recipe contradictory.json
uv run --no-sync python examples/compare_shading_seeds.py contradictory.json
```

前者は完成解が２つあっても、両方とも行列ヒントでは識別不能です。セルヒントを候補に加えると
diagonal-cells の例になります。後者は白連結との同時適用で０解になります。
ヒントや seed の変更ではルールの矛盾を修正できません。どちらも生成を試さず理由を表示します。
診断としての不成立は終了コード0、無効な入力・生成や検証の失敗・不成立な問題のエクスポートは2です。
生成器や診断器の不一致を「その seed が不運だった」として無視しません。

## 比較の範囲

- ４種類の既存黒白ルールの正確な型、９セル以下、８ルール出現以下、異なる seed を１〜８個に限定します。
  seed の範囲は `0..2147483647`。JSON 入力は既存レシピ形式の64 KiB制限と検証を使います。
- [有限選択](finite-shading-generation.md)で識別可能な完成解を選び、既存生成器でヒントを削減します。
  出力問題の唯一解・保存解との一致・ヒント既約性は DSL で検証し、ルールの必要性は独立の有限列挙で計算します。
  反例と全候補ヒントでの比較も JSON に残します。
- 調べた seed の試行だけの比較です。全完成解を列挙する部分と、削減後の問題を標本として比べる部分は異なります。
  必要なルールが多い順に自動選択したり、必ず全ルールが必要な問題を見つけたりはしません。
- 各ルールは他のルールと残存ヒントを固定して１つずつ外します。**個別には冗長でも一括削除はできません。**
  必要性は人間の解法・難易度・面白さ・最小ルール集合とは異なります。
- 最大512配置の有限計算と、最大８回の生成・唯一解検証・ヒント削除検証を行います。
  全体の時間上限はなく、大盤面・カスタムルール・ループとの異種合成には対応しません。
- 環境や依存版が異なる場合の同じ出力、異なる seed で必ず異なる解、一様な分布は保証しません。

## Pythonから保存する場合

`generate_shading.puzzle_record` は完全一致する `ShadingRecipe` と既知の黒白ルールだけを保存します。
保存先の検証・表示と同じ25セル上限をモデル作成前に検査します。候補比較の9セル上限は別途適用されます。
派生クラスや追加部品を持つラッパーを、基礎ルールだけのJSONへ変換することはできません。
対応しないレシピ型・ルール型はモデルを作成する前にエラーになります。派生クラスの実装を単に無視して
保存すると、書き出したルールでは答えが一意に決まらないなど、元と異なる問題になるためです。
自作ルールの問題は、その追加条件を保持できる保存形式と検証APIを使用してください。
