# 既存レシピに制約部品を追加する

`generator.with_constraints(recipe, *builders)` は、既存レシピの基礎ルールに固定の制約を追加します。
完成解の生成と、ヒントを削除して作り直す各モデルに、同じ部品を同じ順で適用します。
`generate` / `reduce_clues` と既存のレシピはそのまま使えます。

## 最小の部品と使用例

`ConstraintBuilder[P]` は、具体的な `Puzzle` 型 `P` を受け取り、DSLの `Constraint` を1個、またはそのイテラブルを返すPython関数です。
新しい制約言語や盤面型を導入せず、既存の式・連結・個数などの制約を使います。

```python
from generator import generate, with_constraints
from puzzle import sum_expr, unique
from puzzle_defs import SlitherlinkRecipe

def six_edges(puzzle):
    return sum_expr(puzzle.edge_on[e] for e in puzzle.board.edges) == 6

recipe = with_constraints(SlitherlinkRecipe(1, 2), six_edges)
clues = generate(recipe, seed=0)
puzzle = recipe.build_from_clues(clues)
puzzle.add(unique())
solution = puzzle.solve()
assert solution is not None
print(clues, puzzle.result(solution))
```

この盤面には基礎ルールだけでは3個のループがあります。6辺を使う制約を足すと外周だけになり、
セル数・辺状態のヒントはすべて削除できます。再検証にも必ず合成後の `recipe` を使ってください。
既存の `SlitherlinkRecipe(..., loop_length=6)` と同じ制約を、部品として表した例です。

[実行例](../examples/compose_recipe_constraints.py)の `selected_count(selector, count)` は、対象の二値変数を選ぶ関数を受け取ります。
個数を数える処理を共有し、変数の意味を選択側で明示します。

| レシピ | selector の対象 | 追加条件 |
| --- | --- | --- |
| 黒白 2×2、黒の非接触 | `black[c]`、`board.cells` | 黒セルが2個 |
| Slitherlink 1×2 | `edge_on[e]`、`board.edges` | セル外周の辺が6本 |
| ヤジリン 3×4、矢印位置なし | `edge_on[e]`、`loop_board.edges` | セル中心間の辺が12本 |

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/compose_recipe_constraints.py
```

例は固定seedで生成し、一意性と、残る各ヒントを1個削除すると一意でなくなることを検査します。
出力は答えを含む比較レポートで、保存問題の形式ではありません。
ヤジリンの例では12頂点をすべて通るため黒セルはなく、辺の異なる2個の候補をヒントで区別します。
黒と辺の結合・非接触・単一ループ自体は元のレシピに残っています。
より大きな盤面や矢印配置全般での生成成功・時間・多様性は保証しません。

## 既存の部品から新しい組合せを作る

まずレシピの寸法・基礎ルールを決め、次に追加条件を新しいモデルへ結び付ける関数を書き、
最後に合成後のレシピで生成・再検証します。
`BlackCount`、`ConnectedWhite` など完成済みの黒白ルールは `ShadingRecipe.rules` に指定できます。
追加条件に使う `connected`、`non_touching`、`sum_expr` などのDSL関数は、新しいソルバーやルールクラスを書かずに再利用できます。

例えば「黒が2個、白も黒もつながる」2×3盤面は次のように作れます。

```python
from generator import generate, with_constraints
from puzzle import connected
from puzzle_defs import BlackCount, ConnectedWhite, ShadingRecipe

base = ShadingRecipe(2, 3, (BlackCount(2), ConnectedWhite()))

def connected_black(puzzle):
    return connected(puzzle.board.cells, lambda cell: puzzle.black[cell])

recipe = with_constraints(base, connected_black)
clues = generate(recipe, seed=0)
```

[完成した実行例](../examples/compose_connected_shading.py)は、この問題を再構築して一意性を検査し、実際のヒントと答えを出力します。
この例の `clues` は `[[行, 列], 値]` の配列で、座標は0始まり、0は白・1は黒です。出力は保存問題ではなく、答えを含むレポートです。

```sh
uv run --no-sync python examples/compose_connected_shading.py
```

`connected` 自体は空の集合を許します。この例では黒2個・白4個なので両方が非空です。
個数条件を外しても非空を要求したい場合は、`at_least_one(...)` も追加してください。
例えば1つの部品から `[connected(...), at_least_one(...)]` のように複数制約を返せます。
従来どおりリスト・タプル・ジェネレーターを返す部品も使えます。

`non_touching(...)` の戻り値は複数の条件を内包する `CompoundConstraint` ですが、そのまま1個のDSL制約として返せます。
ただしこの例に黒の非接触まで加えると、連結した2個の黒セルが隣接できなくなるため解なしになります。
部品がそれぞれ実装済みでも、任意の組合せの成立は保証されません。

`with_constraints` へ渡すのは**新しいモデルを受け取る関数**です。事前に別モデルから作った制約や、
`ConnectedWhite()` のような黒白ルールオブジェクト自体を渡すものではありません。
また `return puzzle.add(...)` や `return rule.apply(...)` は `None` を返すためエラーになります。
DSL制約を `return` するか、完成済み黒白ルールは元の `ShadingRecipe.rules` に指定してください。

## 部品の契約

- 各呼び出しで渡されたモデルから変数を取り出します。別のモデルの変数を閉じ込めて再利用すると、既存のモデル所属検証が拒否します。
- 設定と基礎の盤面構造だけから同じ制約を組み立てます。ヒントの有無・`grid` のヒント値・求解結果・呼び出し回数・変更可能な外部状態で制約を変えてはいけません。
- 元の基礎ルール、盤面、ヒント抽出、回答の射影を変えません。返す制約は追加条件です。`unique()` はパズルの規則ではなく検査指定なので部品に含めません。
- 補助変数を作る場合は、元のレシピが回答変数を明示していることを確認します。この例の3レシピは明示していますが、全登録変数を回答とする別のレシピでは補助代入も別解になります。

`build_from_clues` は元のレシピでヒントを反映した後に部品を適用します。
部品にはヒントも見えるため、「ヒントに依存しない」という契約は実装者が守る必要があります。
関数が呼び出せること、返された単一の値または列挙される項目がDSL制約であること、変数のモデル所属を検査します。
`False` / `True` / `None` や文字列・バイト列は、空の文字列・バイト列も含め `TypeError` です。`unique()` は単一で返しても列挙に含めても `ValueError` になります。
各部品の列挙が終わった時点で、元の回答変数の選択を保っていることも検査します。
選択を空にしたり、一部だけ・補助変数へ変更したりすると `ValueError` です。そうした変更は、
見える盤面に複数の解があっても射影だけを一意に見せてしまうためです。同じ変数の並べ替えや重複は許容します。
回答選択が既定モードのレシピでは、そのモードを維持します。追加のfactory変数も回答に数える従来の動作は変わりません。
この検査は各部品の終了時の選択についてのもので、部品内の一時的な操作やモデル内部の任意の変更を隔離するものではありません。
定数条件を表すDSL式（例えば `sum_expr([]) == 1` は常に不成立）は有効です。
制約もイテラブルも返していない場合は、返すべきものを示す `TypeError` になります。何も追加しない場合は `None` ではなく空のリストなどを返します。
この入口の検査は意味の互換性や単調性の証明ではなく、Python関数の副作用やDSLオブジェクト内部の不正な改変まで検証するものでもありません。

`ConstrainedRecipe` は元のレシピと部品のタプルを保持します。ラッパーを重ねる場合は内側から適用します。
元のレシピは変更されませんが、Python関数や元の設定の内部状態までは凍結しません。
矛盾する追加条件は解なしになり、`generate` は完成解を得られなければ `RuntimeError` になります。
ヒント不足などの失敗は[元の生成契約](generation.md)に従います。

## 合成できる範囲と保存

同じ計算を異なる変数集合へ適用する処理は共有できます。ただし、セル外周の辺とセル中心の辺を自動で対応付けたり、
黒白だけの回答へ辺を追加したりする機能ではありません。そうした変更には、[空間・結合・回答・ヒントを持つレシピ](composition-design.md)が必要です。
既存の固定ルールを削除することもできません。

任意のPython部品を既存のJSON形式へ保存・読込する機能はありません。
既知の個数・連結部品を使う黒白レシピには、別形式の[保存と再構築](composed-recipe-files.md)を使えます。
自作部品は[信頼済みPython側で明示登録](custom-component-registration.md)した凍結データクラスに限り、同じ保存形式で扱えます。
登録済み部品も単一のDSL制約またはその列挙を返せます。未登録のPython関数をデータから再構築する機能はありません。
元の `recipe.base` だけを保存すると追加制約が失われます。既存の保存問題・探索・説明推論CLIへ渡すこともできません。
同じPythonコードと設定から合成レシピを再構築して、生成・求解・ヒント検証を行ってください。
可搬な保存に対応するには、明示した部品名・対象の意味・設定の検証・バージョン管理を備えたデータ形式が別途必要です。

このアダプタ自体には時間上限がありません。小盤面から試し、必要ならプロセスの実行時間を外側で制限してください。
同一seedはソルバーの版や実行環境を跨いだ同一出力や均一抽選を保証せず、唯一解・ヒントの既約性も人間の解きやすさを意味しません。
