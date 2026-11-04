# セル・行個数・列個数を組み合わせる

`ShadingRecipe` はセルの色に加え、行と列の黒マス数もヒント候補として抽出できます。
完成解から指定した種類のヒントをすべて作り、既存の `generate()` / `reduce_clues()` が
一意性を保ちながら削除します。個数ヒントは削除可能な制約であり、基礎ルールではありません。

## 生成して検証する

リポジトリのルートで実行します。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_shading.py generate --rows 3 --cols 4 --rules count non-touching --black-count 3 --hints cell row-count column-count --seed 0 --output mixed.json
uv run --no-sync python examples/generate_shading.py verify mixed.json
uv run --no-sync python examples/generate_shading.py verify examples/shading-mixed-sample.json
```

解を表示せずに試す場合は生成時に `--quiet` を加え、`show mixed.json` で問題を表示できます。
解答の入力と確認は [端末で解いてみる](play-shading.md)を参照してください。

[保存例](../examples/shading-mixed-sample.json)は3×4で、ルールは黒3個と黒の辺接触禁止です。
左端の数字はその行、上端の数字はその列の黒マス数です。`?` は未確定、`.` は白、`#` は黒です。

```text
問題                     解
    1 - - -
2 | ? # ? ?              . # . #
1 | ? ? ? ?              # . . .
- | ? ? ? ?              . . . .
```

セル1個、行個数2個、列個数1個から唯一解になります。この4ヒントはどれも必要です。
全4096盤面を独立に列挙して確かめています。例題 JSON には解も保存しています。

1行目は2列目が黒で、黒を2個置き、辺接触を避けるので、もう1個は4列目に決まります。
黒3個のうち残り1個は2行目にあるため、3行目はすべて白です。
1列目の個数1から残る黒の位置も決まります。

`--hints cell row-count` や `--hints cell column-count` も指定できます。
指定するのは候補の種類です。最終結果に全種類が残ることや、特定種類のヒント数は保証しません。
削除順は seed と候補の順序で決まり、種類ごとの優先度は付けていません。

## なぜセルヒントも候補に入れるのか

行・列の個数を全部与えても、一意とは限りません。3×3で黒3個・黒の辺接触禁止、
全行と全列に黒1個という条件には**6通り**の回答があります。
例えば次の2盤面は同じ個数ヒントを持ちます。

```text
. . #       # . .
. # .       . # .
# . .       . . #
```

`cell` を候補に含めると、初期候補は完成解の全セルを固定します。
一意性を失うセルヒントは削除できないため、必要な追加情報が残ります。
基礎ルールや盤面を変更したり、曖昧な個数ヒントを一意と扱ったりはしません。
上の6解の例では、全セルと個数ヒントから削減すると必要なセルヒントが必ず残ります。

個数だけで作る場合は `--hints row-count column-count` などを指定します。
一意にならなければ生成は失敗し、セルを候補へ加えるよう CLI が案内します。
失敗時には出力ファイルを書きません。個数だけを明示した利用者へセルを黙って追加はしません。
一意になる構成なら個数だけの生成も成功します。例えば既定の4ルール・3×3・黒3個は検証対象です。

## Python API

```python
from generator import generate
from puzzle import unique
from puzzle_defs import BlackCount, NonTouchingBlack, ShadingRecipe

recipe = ShadingRecipe(3, 4, (BlackCount(3), NonTouchingBlack()),
                       clue_kinds=("cell", "row-count", "column-count"))
clues = generate(recipe, seed=0)
puzzle = recipe.build_from_clues(clues)
puzzle.add(unique())
solution = puzzle.solve()
assert solution is not None
print(clues)
print(puzzle.result(solution))
```

| ヒント | Python 表現 | 意味 |
| --- | --- | --- |
| セル | `(Cell(row, col), value)` | `value` は0=白、1=黒 |
| 行個数 | `RowCountClue(row, count)` | 行内の黒マス合計が `count` |
| 列個数 | `ColumnCountClue(col, count)` | 列内の黒マス合計が `count` |

座標は0始まりです。行列個数の座標・個数は非負整数で、盤面の範囲を超える指定を拒否します。
0個、行や列の全マス数と同じ個数も有効なヒントです。ただし基礎ルールと両立するとは限りません。
`clue_kinds` は抽出候補を選ぶ設定で、`build_from_clues()` は渡されたヒントをそのまま適用します。
固定の完成解から作る場合も、`extract_clues(solution, puzzle)` と `reduce_clues(recipe, clues, seed=...)`
を使えます。候補が一意でなければ `reduce_clues()` は `ValueError` を返します。

既定の `clue_kinds=("cell",)` とセルヒントの値表現は維持しています。
型注釈の `Clue` はセルのタプルと2種類の dataclass の union へ広げました。
混在させる呼び出し元は、全要素をタプルとして展開せず `isinstance` などで区別してください。
`build_from_clues` は `Sequence[Clue]` を受け付け、既存のセルヒントのリストも渡せます。

## 保存形式と再現性

セルだけを選ぶ従来のコマンドは `puzzle-box/shading-v1` を出力します。
個数を候補に含めたコマンドは `puzzle-box/shading-v2` を出力し、`clue_kinds` と、
以下の形式のヒントを保存します。検証 CLI は v1 と v2 の両方に対応しています。

```json
[
  {"type": "cell", "row": 0, "col": 1, "value": 1},
  {"type": "row-count", "row": 0, "count": 2},
  {"type": "column-count", "col": 0, "count": 1}
]
```

ルール・寸法・解・seed・実行環境も保存します。v2 の `clue_kinds` は候補順も保持し、
保存ヒントの種類はその候補に含まれている必要があります。
未知のヒント種類や、ヒントオブジェクトの余分なフィールドを拒否します。
同じ環境の別プロセスで生成結果が一致することをテストしていますが、バージョンや OS をまたぐ
同一結果は保証しません。保存物の検証は seed を再実行せず、問題そのものを解き直します。

## 検証と限界

3構成のルール × 3種類の混在設定 × 2 seed を、3×3の全512盤面による検証器と照合します。
保存例は3×4の全4096盤面、行列個数の意味は2×3の全64盤面と全ての有効個数で確認します。
6解の反例、個数だけで成功する構成、保存・読み込み、入力拒否、以前の v1 例題も回帰テストに含みます。

保証するのは、固定ルールの下での唯一解と「どの1ヒントを消しても一意でなくなる」既約性です。
最少ヒント数、セルヒント数の最少化、全種類を残すこと、人間向け難易度は保証しません。
全候補の情報が足りない場合に別の完成解を探し直す処理もありません。
CLI の25マス制限は継続し、実行時間の上限や大盤面性能は未対応です。
このレシピは同じ黒白セルを共有します。異なる回答空間を自動で接続する機能はありません。
