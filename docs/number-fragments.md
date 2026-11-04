# 固定数字と黒白のルールを組み合わせる

`DistinctWhiteNumbers(numbers)` は、同じ行・列の白マスに、同じ固定数字を2個残すことを禁止します。
離れたマスも比較し、途中の黒マスは数字の比較を遮りません。別の行・列や黒マスの数字の重複は許します。
白の存在・黒の非接触・白の連結は別のルールです。

[ニコリの「ひとりにしてくれ」公式ルール](https://www.nikoli.co.jp/ja/puzzles/hitori/)の数字の重複禁止を切り出したものです。
`NonTouchingBlack()` と `ConnectedWhite()` を組み合わせて使えます。
既存の `HitoriPuzzle` とは同じ数字のペアを見つける処理だけを共有し、その入力方針と連結の既存動作を変えません。

## 固定数字から問題を作る

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-hitori-recipe.json --selection finite --seed 0 --output numbered.json --quiet
uv run --no-sync python examples/generate_shading.py show numbered.json
uv run --no-sync python examples/generate_shading.py verify numbered.json
```

[2×3の保存例](../examples/shading-hitori-recipe.json)は固定数字だけで唯一解になり、追加の黒白ヒントが残りません。
数字は生成する回答ではなく**利用者が決める固定入力**です。この機能は数字配置そのものの自動生成・削減を行いません。
別の数字配置では必要な黒白ヒントが残る場合があります。その場合は、通常のひとりにしてくれに黒白ヒントを加えた問題になります。
生成器が確認するのは、固定ルールと残したヒントでの唯一解とヒント既約性です。面白さや人間向けの難易度は保証しません。

`show` は解を隠し、黒白の入力テンプレートと固定数字の表を表示します。
通常の [`check`](play-shading.md) で黒白の回答を確認できます。保存JSONには完全な解も含まれます。

Pythonからは次のように使います。

```python
from generator import generate
from puzzle_defs import DistinctWhiteNumbers, NonTouchingBlack, ConnectedWhite, ShadingRecipe

recipe = ShadingRecipe(2, 3, (
    DistinctWhiteNumbers(((1, 1, 2), (2, 3, 2))),
    NonTouchingBlack(), ConnectedWhite(),
))
clues = generate(recipe, seed=0)
```

## 数字と部屋を同時に表示する

[数字＋部屋の保存例](../examples/shading-number-rooms-recipe.json)は、上の例に「上の行と下の行を別々の部屋とし、各部屋に黒1個」を追加します。
この追加条件はこの例では冗長ですが、数字と部屋が異なる固定データを共有できる再現例です。
同じコマンドの `--recipe` を入れ替えて生成・表示・検証できます。

[Webアプリ](web-app.md)では、黒白セルで「白マスの数字を重複させない」を選ぶと数字入力欄を表示します。
既定の黒2個を外し、黒の非接触・白連結と組み合わせると、上の例を試せます。
数字はセルの中央、黒白の入力状態は隅の印で表示します。黒くしたセルの数字も残り、読み上げ名にも数字を含めます。
部屋ルールを加えると、独立した部屋入力欄と太い境界線も表示します。固定数字や部屋を回答操作で変更することはできません。

## 入力・互換性・限界

- 数字は盤面と同寸の二重配列です。Pythonはリストかタプルを受け、内部で不変タプルにします。JSONは配列だけを受けます。
- 各セルは厳密な整数 `0..99` です。真偽値・小数・文字列・空配列・凹凸のある配列を拒否します。0も有効なラベルです。
- 数字は等しいかだけを比較し、大小や面積の意味を持ちません。部屋ラベルと異なり、数値を振り直しません。
- 保存IDは `distinct-white-numbers`、パラメータは `numbers` だけです。既知ID・厳密な型だけを保存し、サブクラスやファイルからの任意import・実行を許しません。
- UI宣言は `number-grid` 入力と `numbers/cell-numbers` チャンネルです。ブラウザは計画の数字が送信した値と完全一致することを検査し、欠落・不一致は停止します。
- Pythonで複数の異なる数字配置を同じ黒白に課すことはできますが、現在の保存・Web表示は1種類の数字配置だけを扱い、不一致を拒否します。
- Webと有限生成は9セル・8ルール以下、保存CLIは25セル以下です。通常のPython生成には壁時計の時間上限がありません。

数字とルールだけで解がない場合も、複数解でも、人が解きにくい場合もあります。
全組合せが有効になる機能ではありません。[説明推論](shading-deductions.md)はこの数字ルールの手順を持たず、未対応ルール番号を報告します。
検証では小盤面の全回答を数字集合による独立判定と照合し、既存ひとりにしてくれ実装との回答集合も比較します。
任意サイズ・全組合せを検証したことにはなりません。
