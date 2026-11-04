# タテヨコ・ナナメで色をつなぐ

`CornerConnectedColor(black=False, nonempty=True)` は、白マスが辺または頂点を通じてつながることを要求します。
上下左右と斜めを合わせた8近傍であり、斜めだけを許す条件ではありません。
`black=True` なら黒に適用します。`nonempty=False` は対象色0マスも許し、既定値の `True` は少なくとも1マスを要求します。
どちらも厳密な真偽値です。

[ニコリのモチコロ公式ルール](https://www.nikoli.co.jp/ja/puzzles/mochikoro/)には、白い長方形同士が頂点を通じてつながる条件があります。
既存の `RectangularComponents(black=False)` と組み合わせると、各白成分を上下左右では長方形に保ち、それらを角経由で接続できます。
これらだけで完全なモチコロにはなりません。数字・面積・1成分あたりの数字数を表す条件は、この断片には含みません。

## 他のルールの成分は変わらない

この断片が8近傍で調べるのは全体の連結だけです。
`SquareGrid.neighbors`、長方形成分、白い島の面積、黒成分の合計、次数、輪なしなどの上下左右の意味は変更しません。

```text
. #
# .
```

上の白2マスは8近傍ではつながっています。上下左右では別々の1マス成分であり、どちらも長方形です。
`CornerConnectedColor()` は成立し、`ConnectedWhite()` を追加すると解なしになります。
`WhiteIslandAreas(((1, 0), (0, 1)))` と併用しても、数字2つが同じ島になるわけではありません。
一方、1列分の黒マスを挟んで離れた白成分をつなぐことはできません。辺か角を共有する連続した経路が必要です。

`ConnectedWhite()` / `ConnectedBlack()` を残したまま使うと、上下左右の連結条件も残ります。
8近傍連結は、既に課された別の制約を緩めたり置き換えたりしません。

## 長方形を組み合わせた問題を生成する

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-corner-rectangles-recipe.json --selection finite --seed 0 --output corner-rectangles.json --quiet
uv run --no-sync python examples/generate_shading.py show corner-rectangles.json
uv run --no-sync python examples/generate_shading.py verify corner-rectangles.json
```

[2×3の例](../examples/shading-corner-rectangles-recipe.json)は、白の8近傍連結・白成分の長方形・黒2×2禁止・黒3個を組み合わせます。
ルールだけでは複数解があるため、生成器は必要なセルヒントを残します。
生成器は数字の位置や長方形をヒントとして選んでいるのではなく、固定ルールの下で黒白のセルヒントを削減します。
`show` のテンプレートを黒 `#`・白 `.` で埋め、`check corner-rectangles.json --answer "行/行"` に渡すと確認できます。
完全解は画面で隠しますが、保存JSON自体には答えが入っています。

```python
from puzzle_defs import CornerConnectedColor, NoBlack2x2, RectangularComponents, ShadingRecipe, WhiteIslandAreas

# 数字1の白マスが角で接する、セルヒント不要の別の小例。
recipe = ShadingRecipe(2, 2, (
    WhiteIslandAreas(((1, 0), (0, 1))),
    RectangularComponents(False), NoBlack2x2(), CornerConnectedColor(),
))
```

この例の白い島のルールは、すべての白成分に数字を1つ要求します。
モチコロの「数字がない長方形も許す」条件より強いため、モチコロの数字条件全般の代用品にはしないでください。
この断片自体は、白成分を長方形にすることも、数字の存在も要求しません。

## UI・保存・互換性

Webでは「タテヨコ・ナナメで色をつなぐ」を選び、対象色とその非空条件を指定します。
既定で選択されている「白マスをつなぐ」を外すと、上下左右の連結を残さず8近傍連結を試せます。
既存の真偽値入力と `answer/binary-cells` を再利用し、新しい描画器・辺入力は不要です。
部屋・固定数字・面積などの既存表示とも併用できますが、UIの互換性は数学的な成立を保証しません。
黒白以外のプロファイルへこのIDを渡すことはできません。

保存IDは `corner-connected-color`、フィールドは `black` と `nonempty` です。
0/1や文字列を真偽値に変換せず、未知・不足フィールドを拒否します。正確な組み込み型だけを保存し、継承で変えた意味を親型として保存しません。
既存IDの意味は変えません。この新IDを知らない旧版の読み手は拒否します。データからコードを読み込む仕組みではありません。

## DSL から使う

```python
from puzzle import connected

# cells と active は同じ Puzzle に属する既存のセル集合と変数マップ。
constraint = connected(cells, lambda cell: active[cell], diagonal=True)
```

`diagonal` は新しいキーワード専用の真偽値です。省略時は従来どおり `False` で、上下左右だけをつなぎます。
`ConnectedConstraint(cells, indicators)` の直接構築も既定では従来どおりです。
どちらの近傍でも、渡したセル集合以外を通れず、空の選択は許します。対象色の存在は別に要求してください。
親・根・順序の既存の連結エンコーディングを再利用し、選べる隣接対だけを8近傍に広げています。
内部の連結証拠は回答の一意性には含みません。

## 検証と範囲

テストは小盤面の全黒白配置について、親・順序を使うDSLと、距離行列の推移閉包、有限診断の8近傍探索を照合します。
上下左右が既定のままであること、直接構築の互換性、疎なセル集合、空、斜めの鎖、飛び越せない隙間、両色・非空条件、補助変数によらない一意性を含みます。
既存の上下左右を使う求解器、成分の形・面積、Webでの入力と検証も確認します。有限検証から任意サイズの性能は保証しません。

保存CLIは既存の25セル上限、Web・有限診断は9セル上限です。Webは既存の計算予算を使い、通常CLIには壁時計の上限がありません。
この断片の説明可能な推論手順は未対応で、未対応ルール番号として報告します。一意性から人間の解きやすさは判断しません。
