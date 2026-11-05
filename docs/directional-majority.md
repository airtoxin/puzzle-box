# 方向ごとの連続と部屋の多数色数

[ニコリ公式の縦横さん](https://www.nikoli.co.jp/ja/puzzles/juosan/)にある、向きと直交する連続の制限・部屋の多数側の個数を独立した断片として使えます。
回答は既存の黒白セルです。黒を横線、白を縦線に読み替えますが、画面に線分を描いたり、辺のループを作ったりする仕組みではありません。
部屋ごとに異なる数字・数字なしの部屋・線分による回答表示は未対応です。通常の縦横さん全体の実装とは区別してください。

## 方向と直交する連続長を制限する

`DirectionalRunLimit(max_length=2, horizontal_black=True)` は次の条件です。

| マスの色 | 横の連続 | 縦の連続 |
| --- | --- | --- |
| 黒（横向きとして扱う） | 自由 | 最大 `max_length` マス |
| 白（縦向きとして扱う） | 最大 `max_length` マス | 自由 |

`horizontal_black=False` にすると黒白の役割を入れ替えます。
既定の上限2は公式の連続禁止条件に対応し、他の正の整数は変種です。
行と列の両方で両色を制限する `RunLengthLimit` や `NoThreeConsecutive` とは意味が異なります。
横一列の黒3マスは既定で通り、縦一列の黒3マスは通りません。白はその逆です。

対象は盤面全体の横・縦の直線です。斜めや曲がる道を数えず、部屋の境界でも連続は途切れません。
色の存在・個数・連結は要求しません。短い盤面や充分大きい上限では、条件が何も制限しない場合もあります。

## 各部屋の多数側の個数を固定する

`RoomMajorityCount(rooms, count=2)` は、各部屋で `max(黒の個数, 白の個数) == count` を要求します。
同数を許し、多数色が黒か白かは部屋ごとに自由です。黒を `count` 個とする `RoomBlackCount` とは異なります。
例えば4マスの部屋に2を指定すると黒2・白2、3マスに2なら黒2・白1または黒1・白2になります。
2マスに2なら黒2または白2で、色は部屋ごとに変えられます。

この断片は**全ての部屋で同じ `count`** を使います。部屋別の数字配列ではありません。
部屋は固定の連結した分割で、長方形以外も許す拡張です。黒白の部屋内連結や単色は自動では加わりません。
`count` が部屋の大きさより大きい、または半分より小さい部屋があれば矛盾します。
0も入力可能ですが、空でない部屋では成立しません。盤面全体の面積を超える個数は入力エラーにします。

## 3条件の生成例

[3×3の保存レシピ](../examples/shading-directional-majority-recipe.json)では、4・3・2マスの部屋を使います。
部屋配置は `0 0 1 / 0 0 1 / 2 2 1`、多数色の個数は各部屋2、黒は盤面全体で3個です。

```python
from puzzle_defs import BlackCount, DirectionalRunLimit, RoomMajorityCount, ShadingRecipe

recipe = ShadingRecipe(3, 3, (
    DirectionalRunLimit(max_length=2, horizontal_black=True),
    RoomMajorityCount(((0, 0, 1), (0, 0, 1), (2, 2, 1)), count=2),
    BlackCount(3),
))
```

この配置では4解あり、追加の黒白セルヒント2個で唯一解にできます。
方向の制限を外すと18解、多数色の条件を外すと24解、黒の総数を外すと32解です。
どの条件もこの例の完成集合を絞りますが、この有限結果を別の部屋・大きさに一般化することはできません。
セルヒントは縦横さんの通常の部屋数字とは異なり、固定部屋・多数色の指定値そのものを生成・削減する例ではありません。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-directional-majority-recipe.json --selection finite --seed 0 --output directional-majority.json --quiet
uv run --no-sync python examples/generate_shading.py show directional-majority.json
uv run --no-sync python examples/generate_shading.py verify directional-majority.json
uv run --no-sync python examples/generate_shading.py check directional-majority.json --answer "#../#../..#"
```

固定環境の seed 0 では左上の黒・中央の白が残り、上の解答が通ります。
`show` はルール・部屋と残ったセルヒントを表示します。保存JSONには完全解が含まれます。
解答は既存の `check FILE --answer "ROWS"` で、黒を `#`、白を `.` として入力します。
唯一解や追加ヒントの既約性は、人間の難易度・最少ヒント数・固定部屋条件の最少性を保証しません。

## UI・保存・制約の範囲

Webでは「色ごとに横・縦の連続を制限」で上限と黒白の役割を指定し、「各部屋の多数色の個数を固定」で部屋配置と個数を指定します。
上の例は3×3、黒数3、部屋配置を上記の通りにし、初期の白連結を外してセルヒントだけを選べます。
既存の整数・真偽値・部屋の宣言だけで描画し、回答は黒白のセル入力とサーバー検証を使います。
他の部屋ルールと異なる分割を同じ画面・保存問題で使う場合は拒否します。

保存IDは `directional-run-limit`（`max_length`, `horizontal_black`）と `room-majority-count`（`rooms`, `count`）です。
未知・省略フィールド、不正な型、サブクラスを拒否します。データから任意コードを実行することはありません。
古い読込器やスリザーリンク・セル中心ループのWebプロファイルは新IDを拒否します。

方向の条件は長さ `max_length+1` の窓が禁止色だけになることを防ぎます。
多数色の条件は、黒数が `count` または `部屋の面積-count` になることを要求し、同数の場合は同じ条件を2回の排他的選択にしません。
回答の射影は黒白セルだけで、内部の真偽変数は一意性判定の回答には数えません。

テストは1×1・1×3・3×1・2×3・3×2・3×3の全黒白配置を、方向の両設定・上限1と2でCSPと2つの判定に照合します。
独立の判定はセルから逆向きに同色をたどり、窓制約や有限検査器の連続区間集計とは別に数えます。
多数色は個数差の恒等式でも検証し、同数・部屋別の多数色・不可能な個数・共有入力・実生成と解答確認をテストします。
全ての部屋分割や任意のパラメータを網羅した証明ではありません。

Pythonにこの断片専用の盤面上限はありません。保存CLIは25セル、Webと有限選択・診断は9セルまでです。
Pythonの連続長は正の整数で、盤面の最大辺以上なら制約追加を省略し、大きな冗長値をソルバーへ渡しません。Webの入力上限は25です。
説明推論は未対応と報告し、求解・一意性検証では制約を使います。Webの計算予算を維持し、任意の組合せの成立性・実行時間は保証しません。
