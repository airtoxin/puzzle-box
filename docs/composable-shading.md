# ルールを選んで黒白盤面を生成する

既存 DSL 部品を同じマス変数へ適用し、問題の生成・保存・一意性検証までを
つないだ小さな実例です。`ShadingRecipe` は盤面サイズとルールを保持し、既存の
`generate()` が各マスの色ヒントを減らします。生成器にパズル固有の分岐は加えていません。

## まず動かす

リポジトリのルートで実行します。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_shading.py generate --seed 17 --output shading.json
uv run --no-sync python examples/generate_shading.py verify shading.json
uv run --no-sync python examples/generate_shading.py verify examples/shading-sample.json
```

既定は 3×3、黒3個、4ルールすべて有効です。生成結果の JSON は既定では標準出力にも出ます。
解を見ずに遊ぶときは `generate --output FILE --quiet` で保存し、`show FILE` を使ってください。
盤面の入力と解答確認は [端末で解いてみる](play-shading.md)にまとめています。
検証は保存データからモデルを作り直し、解が一意であること、保存した解と一致すること、
残る各ヒントを1つずつ消すと一意でなくなることを確認します。
成功時は `valid`, `unique`, `irreducible` が `true` の JSON を返します。

保存した [例題](../examples/shading-sample.json)は次の問題です。
`?` は未確定、`.` は白、`#` は黒を表します。

```text
問題            解
? ? ?           . . #
? ? ?           # . .
. ? #           . . #
```

ルールは「黒は3個」「黒は辺で接触しない」「白は上下左右で連結し、1マス以上ある」
「白だけの2×2はない」です。この2ヒントから解は1通りに決まります。
この例で各ルールを1つだけ外すと、順に2、5、4、2通りの解になります。
つまり4ルールはいずれも解を絞る役割を持っています。各ヒントも必要です。

## 部品を選ぶ

```sh
uv run --no-sync python examples/generate_shading.py generate --rows 3 --cols 4 --rules count non-touching connected-white --black-count 3 --seed 7
uv run --no-sync python examples/generate_shading.py generate --rules count non-touching --black-count 2 --diagonal --seed 7
```

| Python のルール | CLI 名 | 再利用する DSL | 意味 |
| --- | --- | --- | --- |
| `BlackCount(n)` | `count` | `sum_expr(...) == n` | 黒の総数を固定 |
| `NonTouchingBlack()` | `non-touching` | `non_touching`、隣接ペア | 黒同士の辺接触を禁止 |
| `ConnectedWhite()` | `connected-white` | `connected`、`at_least_one` | 白が非空かつ上下左右で連結 |
| `NoWhite2x2()` | `no-white-2x2` | `windows(2, 2)`、`at_least_one` | 各2×2窓に黒が1個以上 |

上の4種類は既定の組合せです。黒連結、黒2×2禁止、黒の2マス成分、同色3連続禁止、
白黒同数、行列の重複禁止も選べます。[追加6断片の意味と組合せ例](shading-fragments.md)を参照してください。

`--diagonal` は黒同士の角接触も禁止します。`--allow-empty-white` は白0個も許します。
これらのオプションは対応するルールを選んだ場合だけ作用します。
元の `connected` が空集合も許す仕様は変更せず、非空条件を合成ルール側で加えています。
高さまたは幅が1なら2×2窓はなく、`NoWhite2x2` は何も制限しません。

ルールを選べても、必ず両立するわけではありません。例えば2×2で黒4個と非空の白の連結を
指定すると生成は失敗します。CLI は非ゼロ終了し、Python API は `RuntimeError` を返します。
基礎ルールだけで一意なら、ヒントが0個になることもあります。

## Python で組み合わせる

```python
from generator import generate
from puzzle import unique
from puzzle_defs import (
    BlackCount, NonTouchingBlack, ConnectedWhite, NoWhite2x2, ShadingRecipe,
)

recipe = ShadingRecipe(3, 3, (
    BlackCount(3), NonTouchingBlack(), ConnectedWhite(), NoWhite2x2(),
))
clues = generate(recipe, seed=17)  # 既定は (Cell, int) のセルヒント; 0=白、1=黒
puzzle = recipe.build_from_clues(clues)
puzzle.add(unique())
solution = puzzle.solve()
assert solution is not None
print(puzzle.result(solution))
```

`ShadingRule` は `apply(puzzle: Puzzle, board: SquareGrid, black: VarMap) -> None` を持つ
構造的な Protocol です。同じインターフェースの Python オブジェクトで部品を追加できます。
ルールは共有された `black[cell]` に制約を加え、設定と盤面、回答の意味を固定してください。
ヒントを調べて基礎ルールを変えたり、回答変数を選び直したりしてはいけません。
補助変数は作れますが、回答として数えるのは各マスの黒白だけです。
組み込みルールとレシピは frozen dataclass で、レシピはルール列を tuple に保存します。
カスタム部品の不変性や契約の遵守までは自動検証しません。

## 再現性と保存形式

`Puzzle.solve(seed=...)` は乱数 seed に加えて探索 worker 数を1に設定します。
並列探索を使う以前の実装とは、同じ seed でも生成される盤面や速度が異なり得ます。
seed を省略した求解はソルバーの既定設定を使います。同じ実行環境では、別プロセス・異なる
`PYTHONHASHSEED` でも同じ生成結果になることをテストしています。
異なる OR-Tools / Python / OS / モデル構築順での同一結果や、解の均一な抽選は保証しません。

セルヒントだけの JSON の形式識別子は `puzzle-box/shading-v1` です。寸法、ルールとパラメータ、
`[row, col, value]` のヒント、解、seed、Python / OR-Tools のバージョンを保存します。
座標は0始まりです。例題には解も入っているため、プレイヤーへ渡す画面では解を隠す必要があります。
検証時は seed を再実行せず、保存された問題そのものを検証します。
環境情報と seed は記録用で、検証器は環境一致を強制しません。
このファイル形式は[部屋・行列・ピースの6断片](room-fragments.md)、[成分の形の2断片](component-shapes.md)、[固定数字](number-fragments.md)、[連続長上限](run-length.md)、[固定成分サイズ](component-size.md)、[白の可視数](white-visibility.md)、[外枠への接続](component-border.md)、[白い島の面積](white-island-areas.md)、[隣接黒数](adjacent-black-counts.md)、[黒成分の面積合計](black-component-sum.md)、[セルの道の2断片](cell-path-fragments.md)、[部屋の単色と輪なしの2断片](room-uniform-forest.md)、[8近傍の連結](corner-connected-color.md)、[数字なし白成分を許す面積](white-area-clues.md)、[白の端点の丸](white-endpoint-markers.md)、[周囲の黒い連続区間](adjacent-black-runs.md)、[部屋の水位](room-fill-levels.md)、[部屋間の2断片](room-neighbors.md)、[部屋内成分の2断片](room-components.md)、[色を固定しない所属面積](component-area-clues.md)、[成分の角接触](corner-linked-components.md)を含む41種類の組み込みルール専用で、任意のコードを読み込む仕組みはありません。
追加ルールのIDを知らない旧版の読み手は拒否します。既存IDの意味と既定の4ルールは変更していません。
行列個数を含むヒント候補には v2 を使います。両形式を読み込める検証器と
その使い方は [複数のヒント形式](mixed-shading-clues.md)を参照してください。

## 検証と範囲

テストは CP-SAT / DSL を使わない全探索器でも検証します。3×3の全512盤面を、
個数、座標間の距離、白マスの到達可能性探索、2×2窓の直接検査で判定します。
8種類の組み合わせを各2 seed で生成し、一意性・各ヒントの必要性・ソルバーの答えとの一致を確認します。
さらに各ルールを2×2の全16盤面と照合し、保存例題では各ルールを外す比較も行います。
CLI の保存・検証、解を改変したときの拒否、矛盾した組み合わせと0ヒントも対象です。

これは**同じ黒白盤面を共有するルール群**の縦切りです。セルとループ、島番号、
ピース配置、木とテントなど、異なる回答空間を自由につなぐ互換性判定・変換機構は未実装です。
ヒントはセルの色と行・列の黒マス数を選べます。矢印などのヒントは未対応です。
CLI は実験を小さく保つため25マス以下に制限していますが、実行時間の上限ではありません。
ただし[固定成分サイズ](component-size.md)を含むレシピは、Pythonと保存形式も9セル以下に限定します。
API はサイズ上限を設けておらず、大盤面の性能は未検証です。
人間の解き筋、難易度、面白さ、最少ヒント数も保証しません。

行列個数への拡張では、候補ヒント全体でも一意にならないケースを確認し、
セルヒントとの混在で一意性を補えるようにしました。全探索との照合も維持しています。
ヒント種類の優先度や人間向け推論の評価は行いません。異なる回答空間には明示的な接続条件が必要です。

白の連結を証明する補助変数の違いは、別の回答として数えません。
[回答の射影](solver-semantics.md)と[生成契約](generation.md)を使い、削減前後で盤面・基礎ルール・回答の意味を固定します。
