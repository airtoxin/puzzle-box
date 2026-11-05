# 数字から見える白マス数を固定する

`WhiteVisibilityCounts(counts)` は、正の数字が入ったマスを白にし、そこから上下左右にまっすぐ見える白マスの合計を固定します。
自身を1回だけ数え、各方向は最初の黒マスか盤面外で止まります。黒マス自身、黒マスの奥、斜めのマスは数えません。
`0` は数字ヒントのないマスです。白にも黒にもでき、可視数を0にする条件ではありません。

[ニコリの「黒どこ」公式ルール](https://www.nikoli.co.jp/ja/puzzles/where_is_black_cells/)から可視数と数字マスの白を切り出しています。
`NonTouchingBlack()` と `ConnectedWhite()` を加えると、黒の辺接触禁止と白全体の連結も表せます。
この断片だけでは、それらを要求しません。クロットの黒連結成分の面積合計や、ヤジリンの方向付き黒数とは異なります。

## 生成して確認する

固定数字はルールのパラメータで、生成器が削減するセル・行列数ヒントとは別です。生成中に数字や位置は変更しません。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-kuromasu-recipe.json --selection finite --seed 0 --output kuromasu.json --quiet
uv run --no-sync python examples/generate_shading.py show kuromasu.json
uv run --no-sync python examples/generate_shading.py verify kuromasu.json
uv run --no-sync python examples/generate_shading.py check kuromasu.json --answer "#../..#"
```

[2×3の例](../examples/shading-kuromasu-recipe.json)は次の数字と、黒非接触・白連結を使います。
表示上の `.` は可視数を指定しない場所で、保存データでは `0` です。

```text
. 3 2
. . .
```

この設定は追加のセルヒントなしで一意です。別の数字配置は複数解や矛盾になり得ます。
複数解なら、生成器は選ばれたヒント形式で必要なセル等のヒントを残します。固定数字の自動選定・削減をする黒どこ生成器ではありません。
`show` は完全解を隠し、正の数字から分かる白マスは入力済みとして表示します。保存JSON自体には解を含みます。

Pythonでも同じ部品を使えます。

```python
from puzzle_defs import ConnectedWhite, NonTouchingBlack, ShadingRecipe, WhiteVisibilityCounts

recipe = ShadingRecipe(2, 3, (
    WhiteVisibilityCounts(((0, 3, 2), (0, 0, 0))),
    NonTouchingBlack(), ConnectedWhite(),
))
```

## Webの宣言と組合せ

「数字から見える白マス数を固定」を選ぶと、「見える白マス数（0は指定なし）」の入力欄と、丸で囲んだ正の数字が現れます。
正の数字のマスは白として固定し、他のマスと合わせてサーバーへ回答を送ります。0は盤面に表示しません。

宣言は `counts/number-grid` パラメータと `sight-counts/cell-sight-counts` チャンネルです。
既存の `DistinctWhiteNumbers` の `numbers/number-grid`、`numbers/cell-numbers` とは意味も値も別です。
入力の構文が同じでも、パラメータ名が異なる格子は共有しません。各部屋ルールの `rooms/region-map` の共有は維持します。
併用時は、ひとりにしてくれ型の数字を中央、可視数の丸数字を左上に表示します。読み上げにも両方の意味を付けます。
既存の数字0は通常のラベルのままで、可視数の0だけが指定なしです。部屋の境界とも組み合わせられます。

ブラウザは、可視数のチャンネル、要求した値との一致、寸法、整数の範囲を検査します。
未要求・欠落・改変された可視数を黙って描画せず、生成を閉じます。未知の盤面型・ルールは既存どおり拒否します。

## 入力契約と限界

- `counts` は盤面と同じ縦横の、0〜99の整数格子です。真偽値・小数・空配列・凹凸・範囲外・未知フィールドは拒否します。
- 幾何的に達成できない正の数は、有効な入力だが矛盾するルールです。例えば1×1で2は解なしです。
- 保存IDは `white-visibility-counts`、フィールドは `counts` だけです。既知のPython型へ復元し、データからコードは実行しません。未知IDは旧版で拒否されます。
- ファイル/UIの複数の可視数ルールは同じ格子を共有する必要があります。Pythonだけでは異なる格子の制約を重ねられます。
- この断片のPython実装・保存CLI・Webは100セル以下、有限列挙・説明推論は9セル以下です。数字格子の値域は従来どおり0〜99で、可視数100を指定することはできません。通常CLI生成に壁時計の上限はありません。Webは既存のワーカー予算を使います。
- 可視数を使う説明推論は未対応です。唯一解の検証には適用し、手順では未対応番号を報告します。唯一解・既約性は人間の難易度を保証しません。

実装は、各方向の「ここまで全て白」を表す補助変数を双方向のANDとしてつなぎ、その合計に自身の1マスを加えます。
補助変数を偽にして可視数を小さくできないようにし、回答の射影は黒白セルだけに保ちます。
検証は小盤面の全黒白配置を対象に、直線を直接走査する判定と、別実装の白い連続区間長の和でも照合します。
任意サイズ・任意の組合せでの性能や、数字配置の自動発見まで一般化するものではありません。
