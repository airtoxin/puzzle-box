# 独自ルールを作って組み合わせる

黒白盤面では、`apply(puzzle, board, black)` を持つPythonクラスを `ShadingRecipe.rules` に渡せます。
既存のルールと同じ黒白変数へ制約を追加し、元のレシピの生成・ヒント削減・回答の射影を使います。

## 最小の例

「黒マスが1個以上2個以下」を独自ルールにし、既存の「黒マスが辺で接触しない」と組み合わせます。

```python
from generator import generate
from puzzle import sum_expr, unique
from puzzle_defs import NonTouchingBlack, ShadingRecipe

class OneOrTwoBlack:
    def apply(self, puzzle, board, black):
        total = sum_expr(black[c] for c in board.cells)
        puzzle.add(total >= 1)
        puzzle.add(total <= 2)

recipe = ShadingRecipe(2, 2, (NonTouchingBlack(), OneOrTwoBlack()))
clues = generate(recipe, seed=0)
puzzle = recipe.build_from_clues(clues)
puzzle.add(unique())
answer = puzzle.solve()
assert answer is not None
print(clues, puzzle.result(answer))
```

[実行できる例](../examples/custom_shading_rule.py)も同じ手順です。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/custom_shading_rule.py
```

2×2では、黒1個の4盤面と、対角に黒2個の2盤面がこのルールを満たします。
生成器はこの6候補から完成解を取り、区別に必要なセルヒントを残します。
出力は答えを含む実演レポートです。既存CLIが読める保存問題の形式ではありません。

## Pythonの真偽値とDSLの条件を分ける

DSLの変数・式・制約は、まだ解かれていないモデルを表します。Pythonの真偽値として評価できません。
`if`、`and`、`or`、`not`、`bool()`、`any()`、`all()`、連鎖比較でDSLオブジェクトを真偽判定すると
`TypeError` になります。定数だけから作ったDSL制約にも同じ規則を適用します。

特に、次のように書いてはいけません。

```python
puzzle.add(1 <= total <= 2)
puzzle.add((total >= 1) and (total <= 2))
```

Pythonは途中の比較結果を真偽判定します。これを許すと、最初の条件がモデルへ追加されず、
意図と違う問題になることがあります。範囲条件は上の例のように2回 `add` します。

| 意図 | 書き方 |
| --- | --- |
| 両方の制約を満たす | `puzzle.add(a)` と `puzzle.add(b)` |
| 二値変数・条件のうち少なくとも1つが真 | `puzzle.add(at_least_one([x, y]))` |
| 二値変数が偽 | `puzzle.add(x == 0)`、または `puzzle.add(~x)` |
| 条件のうちちょうど1つが真 | `puzzle.add(one_of(a, b))` |
| 解いた後の変数の値を使う | `answer.value(x)` をPythonの整数として判定 |

`at_least_one` に渡せるのは0/1の式です。例えば二値変数や、`x == 1` のような変数比較です。
任意の構造制約を渡せるわけではありません。`one_of` は線形比較または真偽値を表す式を受け取り、
「少なくとも1つ」とは意味が異なります。全制約に `&` / `|` / `~` が使える共通論理式APIはありません。

`Puzzle.add` にPythonの `False` / `True`、`None`、リストなどを渡すこともエラーです。
複数制約は順に追加してください。変数そのものを真に固定するには `add(x == 1)` を使います。
正しい定数制約、例えば `add(sum_expr([]) == 1)` は受理され、モデルを解なしにします。

通常のPython設定に対する `if`、リストの空判定、オブジェクトの同一性を調べる `is` は引き続き使えます。
変数・式の `==` は値の条件を作るので、Pythonオブジェクトの同一性判定には使いません。
この検査はPythonの短絡評価を書き換えるものではなく、すべての誤用を静的に検出する仕組みでもありません。
式の構築自体が補助変数を作る場合があるため、ルール構築中にエラーになったモデルは作り直してください。

## 固定する意味と未対応の範囲

独自ルールは毎回渡されたモデルの変数を使い、ヒントの有無や呼び出し回数で条件を変えてはいけません。
設定・盤面・回答の意味を固定する[生成契約](generation.md)に従います。
生成後の確認にも同じ独自ルールを含むレシピを使ってください。

この入口は黒白セルの共通盤面向けです。ループ辺や他の回答空間との接続には、変数・射影・ヒントを揃えた
[別のパズル定義やレシピ](composition-design.md)が必要です。ルール同士の成立性は自動では保証しません。
独自PythonクラスのJSON保存、既存CLIでのルール表示・組合せ探索・説明推論には対応していません。
可搬な保存形式を作る場合は、部品名・設定・対象座標・版の意味を別途定義する必要があります。
