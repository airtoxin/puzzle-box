# 別の回答空間で試す：スリザーリンク形式の生成

`SlitherlinkRecipe` は、**使用する辺の集合を回答にする**生成レシピです。
既存の `SlitherlinkPuzzle`、単一ループ・個数の制約、解の射影、汎用生成器を再利用します。
新しい万能ルール型は作らず、非空の単一ループに、任意の長さ指定と2種類のヒントを組み合わせます。

## 動かす

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_slitherlink.py generate --rows 2 --cols 2 --loop-length 8 --seed 2 --output loop.json --quiet
uv run --no-sync python examples/generate_slitherlink.py show loop.json
uv run --no-sync python examples/generate_slitherlink.py verify loop.json
uv run --no-sync python examples/generate_slitherlink.py verify examples/slitherlink-sample.json
```

`--quiet` は解を含む JSON の画面出力を抑えます。指定する場合は `--output` が必要です。
保存した [例題](../examples/slitherlink-sample.json)は、2×2の盤面で全8辺のループを作る問題です。

```text
+ ? + ? +
? . ? 3 ?
+ ? + ? +
? . ? . |
+ ? + ? +
```

数字はそのマスの周囲で使う辺の本数です。`.` は数字ヒントなし、`+` は頂点、
`?` は未確定の辺です。`---` と `|` は使う辺の指定、`x` は使わない辺の指定です。
この例では右上の数字3と、右下の外周辺を使う指定だけを与えます。
この2ヒントはどちらも必要です。長さ8を外すと、右列を囲む6辺のループも成立し、2解になります。

`show` の入力用テンプレートを埋め、`check FILE --answer "辺の段"` で完成解を確認できます。
入力形式・終了コード・検証の範囲は[ループを解いて確認する](play-slitherlink.md)を参照してください。

解を表示するときだけ次を実行します。

```sh
uv run --no-sync python examples/generate_slitherlink.py show loop.json --solution
```

`--loop-length` を省くと長さは固定しません。
`--hints cell-count` は数字だけ、`--hints edge` は辺指定だけ、既定値は両方です。
指定は候補の種類で、削減後に両方が残るとは限りません。

## 数字だけでは足りない反例

2×2の全マスに次の数字を入れても、8辺の異なるループが2つ成立します。

```text
3 2
2 3
```

全4096通りの辺配置を列挙して確認しています。全数字が同じなので、数字の削除方法を変えても
この曖昧さは解消しません。`cell-count` だけを指定した生成は、候補が一意でなければ失敗します。
別の完成解を探し直す処理や、辺ヒントを黙って追加する処理はありません。

既定の候補集合は、数字に加えて全ての辺の使用・不使用も含みます。
これなら初期候補が完成した辺集合を固定し、削減時に必要な辺指定を残せます。
ループ方向などの補助変数は回答に含めず、同じ辺集合を別解とは数えません。

## Python API と再利用した部分

```python
from generator import generate
from puzzle import unique
from puzzle_defs import SlitherlinkRecipe

recipe = SlitherlinkRecipe(2, 2, loop_length=8,
                           clue_kinds=("cell-count", "edge"))
clues = generate(recipe, seed=2)
puzzle = recipe.build_from_clues(clues)
puzzle.add(unique())
solution = puzzle.solve()
assert solution is not None
print(puzzle.result(solution))  # set[Edge]
```

| 部分 | 実装での再利用 |
| --- | --- |
| 盤面・辺・頂点 | `SquareGrid`, `Cell`, `Vertex`, `Edge` |
| 単一ループと頂点の次数 | 既存 `SlitherlinkPuzzle` の `single_cycle`、次数0または2 |
| 非空条件 | `at_least_one(edge_on)` をレシピで追加 |
| 任意の長さ指定 | `sum_expr(edge_on) == loop_length` |
| 数字ヒントの抽出 | 既存 `SlitherlinkPuzzle.extract_clues()` |
| 回答の同一性 | `set_solution_vars(edge_on)` で見える辺だけを選択 |
| 作問 | 既存 `generate()` / `reduce_clues()` を変更せず使用 |

`single_cycle` と元の `SlitherlinkPuzzle` が空の辺集合を許す仕様は変更していません。
このレシピが非空を要求します。したがって1×1ではヒント0個で唯一の四角いループになります。
長さ0や奇数など、他の条件と両立しない指定は求解・生成に失敗します。

ヒント型は `CellEdgeCountClue(Cell(r, c), count)` と `EdgeStateClue(Edge(a, b), used)` です。
座標は0始まり、数字は0〜4（既存定義と同じ範囲）、辺の状態は0/1です。
辺は上下左右に隣接する頂点を結び、逆向きの指定は同じ無向辺へ正規化します。
範囲外・不正な値を拒否し、矛盾する重複ヒントは上書きで消さずモデルでも矛盾として扱います。
削減中は寸法・非空条件・長さ・回答変数を固定し、ヒントの制約だけを取り除きます。

## 何が共通で、何がまだ接続されていないか

| 組み合わせ | 対応範囲 |
| --- | --- |
| 単一非空ループ＋長さ＋数字＋辺指定 | このレシピで生成・唯一解・既約性を検証できる |
| 黒白レシピとループレシピで同じ生成器を使う | 対応。3操作の生成契約と解の射影を共有する |
| 黒白のセル色ヒントをループ数字として渡す | 非対応。意味が違うため新レシピは専用ヒント型を要求する |
| 黒白の非接触・白の連結を辺マップへそのまま適用する | 非対応。セルと辺の対応・制約の意味を定義する必要がある |
| 黒白とループを同じパズル内で組み合わせる | このレシピでは未対応。別の[ヤジリン生成例](yajilin-composition.md)で明示的な接続条件を実証 |
| 領域・ピース・対応付けとの自動接続 | 未実装。候補空間と回答の意味を決める必要がある |

既存の [ヤジリン](../packages/puzzle-defs/src/puzzle_defs/puzzles/yajilin.py)は、
マスを双対グリッドの頂点に対応させ、`次数 + 2 × 黒マス = 2` で黒白と辺をつないでいます。
これは単に2つのルール名を並べるだけでは得られない接続条件です。
このレシピの `Edge` はマスの外周なので、ヤジリンのマス間を結ぶ辺とも意味が異なります。

[ヤジリン生成例](yajilin-composition.md)では、矢印マスの位置を固定して数字だけを削除し、
マスの役割を維持しています。既存の `result()` が返すセル状態に加え、ループ辺も回答として
射影・保存・検証します。自動的なルール互換性の仕組みには一般化していません。
保存形式と表示も別スクリプトにしています。

## 検証と限界

2×2の全4096辺配置を、CP-SAT / DSL を使わず次数と到達可能性で検査すると13ループになります。
4種類の長さ設定 × 2種類の候補集合 × 2 seed の生成結果をこの全集合と照合します。
全13ループの数字だけの一意性、2解の反例、分離した2ループの拒否、補助変数を加えても
辺集合の一意性が変わらないこと、JSONの保存・再検証・入力拒否も対象です。

保存形式は `puzzle-box/slitherlink-v1` です。寸法、長さ、候補順、ヒント、解の辺集合、seed、
Python / OR-Tools のバージョンを含みます。辺は `[row1, col1, row2, col2]` で保存します。
同じ実行環境の別プロセスで生成結果が一致することを確認しますが、バージョン・OSをまたぐ
同一出力や均一な抽選は保証しません。保存した問題の検証は seed を再実行せず行います。

CLI は9マス以下に制限しますが、実行時間の上限ではありません。
大盤面性能、最少ヒント数、人間向けの難易度・解き筋、途中解答の確認や描画GUIは未対応です。
黒白と辺のレシピは同じ生成契約・求解基盤を使い、それぞれの意味を独立した検証器で確認します。
この共通性は、任意ルールの自動接続を意味しません。
