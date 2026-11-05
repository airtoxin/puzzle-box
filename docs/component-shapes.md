# 連結成分の形を組み合わせる

`ShadingRecipe` に、選んだ色の各連結成分を長方形にする条件と、長方形以外にする条件を追加できます。
ここで連結とは上下左右の接触です。正方形・1マス・幅1の帯も長方形に含めます。斜めの接触は成分をつなぎません。

| Python / 保存・Web ID | 条件 | 既定の対象色 |
| --- | --- | --- |
| `RectangularComponents(black=True)` / `rectangular-components` | 対象色の各成分が、穴のない長方形を埋める | 黒 |
| `NonRectangularComponents(black=False)` / `nonrectangular-components` | 対象色のすべての成分が長方形以外 | 白 |

`black` は厳密な真偽値で、`False` なら白が対象です。色の個数や存在は指定しません。
その色が0マスなら、どちらの条件も満たします。必要な存在・個数は `BlackCount` などの別ルールで指定してください。

[ニコリのチョコバナナ公式ルール](https://www.nikoli.co.jp/ja/puzzles/choco_banana/)は、黒成分を長方形、白成分を長方形以外とし、
数字のあるマスではその成分の面積を指定します。この2断片は形の条件を再利用したものです。
この2断片だけには数字マス・成分の面積ヒントを含みません。
数字も使う場合は、色を固定しない [ComponentAreaClues](component-area-clues.md) を組み合わせられます。そちらには9セル上限があります。
既存の専用パズルクラスの意味は変えません。

## 保存例から生成する

リポジトリのルートで実行します。出力先には既存ファイルと異なる名前を選んでください。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-choco-shapes-recipe.json --selection finite --seed 0 --output shapes.json --quiet
uv run --no-sync python examples/generate_shading.py show shapes.json
uv run --no-sync python examples/generate_shading.py verify shapes.json
```

[例のレシピ](../examples/shading-choco-shapes-recipe.json)は2×3で、黒成分が長方形、白成分が長方形以外、黒2個を組み合わせます。
条件に合う完成解は8通りです。セルヒントを削減して唯一解にし、通常の `show` では解を隠します。
表示したテンプレートから[解答を確認](play-shading.md)できます。保存JSONには解が入ります。
同じ環境・seedなら再現できますが、依存ライブラリや環境をまたいで同じ問題になる保証はありません。

Pythonでも同じ部品を使えます。次の例では白の各成分を長方形にします。

```python
from generator import generate
from puzzle_defs import BlackCount, RectangularComponents, ShadingRecipe

recipe = ShadingRecipe(2, 3, (RectangularComponents(black=False), BlackCount(2)))
clues = generate(recipe, seed=0)
```

[Webアプリ](web-app.md)の黒白セルでは2つの条件を選び、それぞれの「黒を対象にする」を切り替えます。
既存の真偽値パラメータと `answer/binary-cells` を再利用し、専用の描画器や形の番号は追加しません。
既定の黒2個を残し、白連結を外し、黒の長方形と白の長方形禁止を選ぶと、上の組合せを試せます。
ファイルやWebから任意コードを取り込む機能はありません。既知ID・厳密なパラメータだけを受理し、未知IDは拒否します。

## 組合せの注意

- 「すべての成分が長方形以外」は、「すべての成分が長方形」の単なる否定とは異なります。L字と孤立1マスが混在すると、どちらの条件も満たしません。
- 同じ色に両方を課すと、その色は0マスに決まります。黒2個なども課せば矛盾します。
- `BlackDominoes()` は黒成分を1×2または2×1にするため、黒の `RectangularComponents()` は冗長です。
- 長方形以外の成分は少なくともL字の3マスが必要です。縦か横が1マスの盤面では、その色が1個でもあると長方形禁止に反します。
- 長方形以外を課した成分の中に、小さい長方形の部分集合があっても構いません。判定対象は成分全体です。

## 符号化と限界

長方形の条件は、2×2窓の対象色がちょうど3個になる凹角を禁止します。
この局所条件から各上下左右連結成分が長方形になる性質を使った符号化であり、公式ルールがこの実装方法を指定しているわけではありません。
長方形禁止では、既存の `enumerate_rectangles` で軸に沿うすべての長方形を列挙し、「内部がすべて対象色で、外周に同色の隣接セルがない」を禁止します。
盤面の外にはセルを仮定せず、端に接する成分・盤面全体・1マスも検査します。

後者の節数は `rows*(rows+1)*cols*(cols+1)/4` で、各節に内部と外周のセルを含めます。
保存CLI・黒白Webは最大100セル、Webは最大8ルールです。有限選択・診断は9セルまでです。組み合わせるルールに固有の上限があれば、より小さい方が適用されます。Webは時間予算付きで、通常CLI生成には壁時計の上限はありません。
Pythonで直接 `generate` する場合には壁時計の時間上限がありません。Webの計算予算と未確定結果の扱いは維持します。

有限検査はDSLと異なり、成分を列挙して外接長方形の面積と成分サイズを比較します。
小盤面の全回答を照合していますが、任意サイズや全ルール組合せの検証ではありません。
[説明推論](shading-deductions.md)にこの2断片の手順はなく、該当番号を `rules_without_deductions` に残します。
唯一解であることと、実装済み手順や人間に解けることは別です。
