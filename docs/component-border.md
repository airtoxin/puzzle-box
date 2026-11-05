# 全ての成分から外枠へ到達させる

`ComponentsTouchBorder(black=True)` は、黒の各連結成分に、盤面の端のマスを1つ以上含むことを要求します。
同じ色の上下左右のマスだけを通って端へ到達する必要があり、斜めの接触や、途中で反対色を通る経路は使えません。
`black=False` なら白を対象にします。対象色が0個でもよく、外枠に接する複数の成分が互いに離れていても構いません。
盤面内で全てを1成分にする `ConnectedBlack()` / `ConnectedWhite()` とは異なります。

これは [GMPuzzles の Cave](https://www.gmpuzzles.com/blog/cave-rules-and-info/) の「黒の各成分が外枠へつながる」条件を切り出したものです。
数字から見える白マス数と白全体の連結を組み合わせます。ここでの Cave は黒白セルによる規則で、旧来の BAG の境界線や単一ループを生成する規則とは区別します。

## Cave の合成例

```python
from puzzle_defs import ComponentsTouchBorder, ConnectedWhite, ShadingRecipe, WhiteVisibilityCounts

recipe = ShadingRecipe(3, 3, (
    WhiteVisibilityCounts(((5, 3, 5), (0, 0, 0), (0, 0, 0))),
    ConnectedWhite(), ComponentsTouchBorder(),
))
```

[固定数字の3×3例](../examples/shading-cave-recipe.json)を保存・表示・検証できます。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-cave-recipe.json --selection finite --seed 0 --output cave.json --quiet
uv run --no-sync python examples/generate_shading.py show cave.json
uv run --no-sync python examples/generate_shading.py verify cave.json
uv run --no-sync python examples/generate_shading.py check cave.json --answer ".../.#./.#."
```

数字と白連結だけでは、中央だけが黒の解と、中央から下端まで黒が伸びる解の2通りがあります。
黒の外枠到達を加えると中央だけの黒を除き、一意になります。追加のセルヒントは不要です。
黒2個は辺で接するので、黒どこ用の `NonTouchingBlack()` をここに足すと矛盾します。
一般の Cave に黒2×2禁止は要求していません。固定数字の自動生成・削減はしません。他の入力では追加ヒントが必要な場合があります。

Web では3×3を選び、「数字から見える白マス数を固定」に次の3行を入力し、白連結と「全ての連結成分を外枠につなぐ」を有効にします。
黒総数など既定の別条件を外し、対象色は黒を選びます。既存の黒白盤面・可視数・回答確認をそのまま使います。

```text
5 3 5
0 0 0
0 0 0
```

## 白を外枠へつなぐ例

`ConnectedBlack()`・`NoBlack2x2()`・`ComponentsTouchBorder(False)` なら、黒を1つにつなぎ、全黒2×2を禁止し、囲まれた白を除けます。
これは [Coral 型の説明](https://www.gmpuzzles.com/blog/2013/11/melon-puzzle-18-pento-coral/)で使われる配置条件です。
この合成は行列の連続長ヒントやピース配置を実装せず、完全な Coral 出題形式ではありません。
[3×3の配置例](../examples/shading-coral-shape-recipe.json)では、黒総数7も加えています。必要な追加の黒白ヒントは生成器が残します。
白を外枠へつなぐ条件を外すと許される、囲まれた白がある配置も含めて比較できます。

## 実装と範囲

既存の `connected` を、元の盤面と、その外側に1マス幅で足した仮想フレームへ適用します。
フレームは四隅を含めて固定で対象色にし、全側面をつなぎます。元の各成分が端に接すれば、フレームを介して全体が連結します。
逆に、端に接しない成分はフレームへ到達できません。仮想マスと連結の補助変数は回答・ヒントに含めません。
フレームを盤面上の経路と誤認したり、元の盤面内で成分同士の接触を強制したりしません。

保存IDは `components-touch-border`、パラメータは厳密な真偽値の `black` だけです。整数0/1、未知フィールド、意味を変え得るサブクラスは保存形式で拒否します。
UI は同じ真偽値の宣言と既存黒白チャンネルで描画でき、ブラウザにルール固有の分岐を追加しません。
外枠は長方形盤面の4辺です。幅か高さが2以下なら全マスが端なので、この断片は何も絞りません。穴のある盤面の内周や、斜め連結は対象外です。

保存CLI・黒白Webは最大100セル、Webは最大8ルールです。有限選択・診断は9セルまでです。組み合わせるルールに固有の上限があれば、より小さい方が適用されます。Webは時間予算付きで、通常CLI生成には壁時計の上限はありません。
この断片の説明推論は未対応で、唯一解の事前検証では使い、推論の未対応番号を残します。人間向けの難易度や全サイズの性能は保証しません。
独立検査は元の盤面内の成分と端の接触を調べ、テストでは端からの多点始動の探索とも照合します。
黒と白それぞれの3×3全配置、細い盤面、斜めだけの接触、分離した複数の端の成分、Cave と白外枠の合成を扱います。
