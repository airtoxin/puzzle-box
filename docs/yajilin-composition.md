# 黒マスとループをつなぐ小さな生成例

`YajilinRecipe` は、黒白セルとセル中心を通るループを同時に決めるレシピです。
既存ヤジリンの「黒マスなら次数0、白マスなら次数2」という制約を再利用し、
数字・黒白の指定・辺の指定を共通の生成器で削減します。
片方の決定がもう片方の可能性を変える、具体的な異種合成です。

これは**固定の矢印マスと、補助のセル・辺ヒントを持つヤジリン形式の変種**です。
通常のヤジリンの数字だけで必ず唯一解を作れる、という機能ではありません。

## 保存例を試す

リポジトリのルートで実行します。Python 3.12以上とuvが必要です。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_yajilin.py show examples/yajilin-sample.json
uv run --no-sync python examples/generate_yajilin.py verify examples/yajilin-sample.json
uv run --no-sync python examples/generate_yajilin.py show examples/yajilin-sample.json --solution
```

問題の盤面部分は次のようになります。

```text
 .  ?  .  ?  .  ?  .
       ?     ?     ?
>0     .  ?  .  ?  .
       ?     ?     |
 .  ?  .  ?  .  ?  .
```

- `>0` は右方向に黒マスが0個というヒントです。このマス自体は黒にもループにも使いません。
- `.` は未確定の普通のマス、マス間の `?` は未確定の辺、`|` は使用する辺のヒントです。
- すべての普通のマスを黒マスかループ上の白マスにします。黒マスは縦横に隣接できません。
- すべての白マスを、分岐・交差しない1本の非空ループで通ります。
- 矢印は盤面の端まで数え、別の矢印マスがあればそこだけを飛ばします。

答えは黒マス3個とループ8辺です。数字を外しても、辺ヒントを外しても2解になります。
両方を残すと1解であることを、独立した全列挙でも確認しています。
`show` は通常はヒントだけを表示し、`--solution` のときだけ全回答を表示します。
`verify` は**黒マスとループの両方**が保存した答えに一致するかを確認します。

```sh
uv run --no-sync python examples/generate_yajilin.py generate --seed 6 --output coupled.json --quiet
uv run --no-sync python examples/generate_yajilin.py show coupled.json
```

既定は3×4、矢印位置は0始まりの `(1, 0)`、方向は右、候補は `arrow edge` です。
`--arrow ROW COL DIRECTION` を繰り返すと位置・方向を指定できます。
`--hints arrow black edge` なら黒白指定も候補になります。
採用した候補の種類が、削減後にすべて残るとは限りません。
`--quiet` は `--output` と一緒に使います。保存JSONには答えも含まれます。

## Pythonから組み合わせる

```python
from generator import generate
from puzzle import Cell, unique
from puzzle_defs import ArrowSite, YajilinRecipe

recipe = YajilinRecipe(
    rows=3,
    cols=4,
    arrow_sites=(ArrowSite(Cell(1, 0), "right"),),
    clue_kinds=("arrow", "black", "edge"),
)
clues = generate(recipe, seed=6)
puzzle = recipe.build_from_clues(clues)
puzzle.add(unique())
solution = puzzle.solve()
assert solution is not None
answer = recipe.answer(solution, puzzle)
print(answer.black_cells, answer.loop_edges)
```

`build_from_clues` は候補ポリシーに関係なく3種類の型付きヒントを受け取れます。
`clue_kinds` は抽出する候補とその順序を指定します。`EdgeStateClue` は
[ループレシピ](slitherlink-composition.md)と同じ型を使いますが、座標の意味は異なります。
Slitherlinkのマスの角を、ヤジリンのセル中心として自動変換することはありません。
JSON形式も別にし、他のレシピの保存記録をそのまま読み込むことを拒否します。

| 構成要素 | この例での扱い |
|---|---|
| 黒マス同士の非隣接 | 既存 `YajilinPuzzle` の縦横隣接制約 |
| 非空の単一ループ | 既存 `single_cycle` に非空条件を追加 |
| 異種の接続 | 各普通セルで `接続する使用辺の数 + 2 × 黒 = 2` |
| 矢印マス | 黒変数を持たず、接続する辺をすべて未使用に固定 |
| 数字ヒント | 矢印方向の普通セルの黒変数を合計 |
| 黒白・辺のヒント | 対応する変数の0/1を固定 |
| 回答の射影 | 普通セルの黒変数と全辺の使用変数 |
| 生成・ヒント削減 | 既存 `generate` / `reduce_clues` を変更せず再利用 |

すべての辺が決まれば次数から黒マスも決まりますが、公開する回答の両方を明示して射影・保存・検証します。
逆に、黒マスだけでは辺が決まるとは限りません。
**矢印のない3×4で全マス白という同じ黒白配置に、2種類のループがあります。**
黒変数だけに射影すると誤って唯一解と判定できてしまう反例と、辺ヒントを残すと一意にできることをテストしています。

## ヒント削減で固定するもの

矢印マスを数字と一緒に消して普通のマスに戻すと、黒変数とループの経路が増えます。
元の答えの意味まで変わるため、通常の制約削減として扱えません。
位置と方向はレシピに固定し、数字だけを削除します。
数字を削除したマスは `>?` などと表示し、通行不可のまま残します。

既存 `YajilinPuzzle` には任意のキーワード引数 `reserved_clue_cells` を追加しました。
元の呼び出し、既存の矢印数字、`result()` のセル状態返却は維持しています。
`loop_board` はセル中心の双対グリッドです。完全な回答はレシピの `answer()` で取得します。
同じ位置に矛盾するヒントを2つ渡しても、後の値で前の制約を消しません。

固定位置がループを妨げる場合もあります。たとえば2×2に矢印マスを1つ置くと不成立です。
生成は `RuntimeError` になり、矢印を勝手に移動しません。
`clue_kinds=("arrow",)` や `("black",)` で抽出したヒントが一意でなければ `ValueError` です。
既定の1回生成では別の完成解を探索し直しません。辺ヒントの暗黙の追加もしません。
確実に完成した回答を固定する候補が必要なら `edge` を含めます。

## 数字だけで生成したい場合の有限回探索

同じ矢印配置でも、選ばれた完成解によって数字だけで一意になる場合とならない場合があります。
3×4、矢印 `(1, 0, right)`、候補 `arrow` を固定した小規模実験では、Python 3.12.14 /
OR-Tools 9.15.6755で seed 0〜11 のうち0・5・8が成功し、他の9個は候補ヒントが曖昧でした。
これは固定した12 seedの観察であり、成功確率や均一なランダム抽選を意味しません。

CLIで `--attempts` を指定すると、固定位置・規則・ヒント形式を保って連続するseedを試せます。

```sh
uv run --no-sync python examples/generate_yajilin.py generate --hints arrow --seed 6 --attempts 3 --output arrows.json --quiet
uv run --no-sync python examples/generate_yajilin.py show arrows.json
uv run --no-sync python examples/generate_yajilin.py verify arrows.json
```

この環境では6・7が失敗し、8で数字ヒント1つだけの唯一解を生成できます。
追加した辺・黒白ヒントはありません。成功時点で停止します。
既定値は1回、指定範囲は1〜32回です。試すseed全体が0〜2147483647に収まる必要があります。
上限まで一意な候補を得られなければ失敗し、保存先の既存ファイルは変更しません。

保存JSONの `seed` は**成功したseed**です。複数回探索を指定したときだけ、`generation` に
`initial_seed`、`attempt_limit`、`attempts_used` を追加します。成功したseedを通常の1回生成に渡すと、
同一環境で同じ答え・ヒントを再現できます。既存のv1記録も引き続き読み込めます。
検証はメタデータの整合と回答の唯一性を確認しますが、過去の試行履歴そのものは再実行しません。

再試行の対象は、初期候補が唯一解検査を通らなかった場合だけです。入力エラー・レシピの実装エラー・
完成解を求められない固定配置などは、そのまま失敗します。汎用生成器の新しい例外
`InitialCluesNotUniqueError` は既存の `ValueError` を継承するため、既存の捕捉は維持されます。
この例外自体はソルバーの状態分類ではなく、矛盾した候補や一意性を証明できない場合も含みます。

試行数の上限は経過時間の上限ではありません。また連続seedが異なる完成解を返す保証もなく、
探索の網羅性・成功・人間向けの難易度は保証しません。APIの `generate()` は従来通り1回だけです。

## 検証と限界

- 独立した検査器が3×4の全131,072辺配置を列挙し、次数と連結性から40種類の単一ループを抽出。
  矢印マスの除外、残りの黒マス、非隣接条件を別に判定し、複数の固定配置でソルバーの全回答と一致。
- 2つの配置 × 3つの候補ポリシー × 2 seed の生成を検査器と照合し、唯一解と各ヒントの必要性を確認。
- 黒白配置が同じ2ループ、補助変数の除外、矢印の4方向、空の射線、矢印を飛ばす計数、
  削減前後のセル役割、矛盾した重複、入力境界、保存答えの改変を検査。
- 同じ環境・同じseedの別プロセスで生成結果が一致。Python・OR-Tools・OSをまたぐ同一出力は保証しない。

CLIは12マス以下に限定しています。これは時間制限ではなく、大盤面の性能や実行時間上限は未検証です。
得られるのは候補集合に対して1個ずつ削除できないヒント集合で、最少ヒント数や人間向け難易度を保証しません。
進行中の解答入力・手筋説明・ヒント提示UIはありません。表示は英語ASCIIです。

この実例で、黒白とループの**明示的な接続条件を持つ合成**を生成契約に載せられました。
任意の黒白ルール・ループルール・領域ルールを名前だけで組み合わせる仕組みには一般化していません。
次に接続条件を抽出するなら、盤面座標、固定セルの役割、回答変数、ヒントが除去できる範囲を宣言する必要があります。
矢印位置自体の生成は、制約削減とは別の探索として扱うのが候補です。

## PRの依存関係

この変更は #12 `codex/slitherlink-recipe` を土台にし、`EdgeStateClue` と例の辺JSON変換を再利用します。
#12 は #9 の再現可能なseed設定と、#2〜#8の求解・生成基盤を含みます。
`#9 → #10 → #11` の黒白ヒント・端末体験とは別の `#9 → #12 → この変更` という系列です。
共通のソルバー・生成器を変更せず、両系列を合わせて検証します。
#2〜#8 は main に採用済みです。合成機能の現在の base・レビュー・採用状況は
[PR #13](https://github.com/airtoxin/puzzle-box/pull/13) とレビューガイドを参照してください。
親を採用した後は実際の main と差分を再確認します。

上記の有限回探索は、その後の #13 `codex/yajilin-composition` を土台にした追加変更です。
既定の生成回数や、ヒント形式・矢印位置を維持する契約は変更していません。
