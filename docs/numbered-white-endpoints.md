# 端点と可視数を組み合わせて数字付きの丸にする

数字付きぬりみさきは、既存の [端点の丸](white-endpoint-markers.md)と[白の可視数](white-visibility.md)を組み合わせて表せます。
丸が白の端点なら、白い隣は1つだけです。他の3方向は黒か盤外なので、四方向の可視数は、その1方向へまっすぐ続く白マス数と一致します。
丸自身を1回含み、最初の黒または盤端で止まります。曲がった先や、黒の向こうは数えません。

[ニコリの公式ルールと解答図](https://www.nikoli.co.jp/ja/puzzles/nurimisaki/)の左上の3は、丸自身と続く白2マスに対応します。
この数え方で既存の `WhiteVisibilityCounts` を再利用します。新しい求解制約や保存IDは追加しません。

## Pythonで安全に束ねる

```python
from puzzle_defs import ConnectedWhite, NoBlack2x2, NoWhite2x2, ShadingRecipe, numbered_white_endpoints

recipe = ShadingRecipe(2, 3, (
    *numbered_white_endpoints(
        ((1, 0, 0), (0, 0, 1)),  # 丸の位置
        ((3, 0, 0), (0, 0, 2)),  # 丸自身を含む直線長
    ),
    ConnectedWhite(), NoWhite2x2(), NoBlack2x2(),
))
```

`numbered_white_endpoints(markers, lengths)` は、`WhiteEndpointMarkers` と `WhiteVisibilityCounts` の2要素タプルを返します。
`*` でレシピのルール列へ展開します。関数自体はルールや登録済みビルダーではなく、上限8ルールのうち2個を使います。
白の連結と黒白の2×2禁止は、呼出し側で別に加えます。

| データ | 意味 |
| --- | --- |
| `markers` の0 / 1 | 丸なし / 丸あり |
| `lengths` の0 | 数字なし。丸の有無は `markers` が決める |
| `lengths` の正の数 | 丸自身を含む直線長。丸のある場所にだけ指定できる |

格子は同寸の長方形で、マーカーは厳密な整数0/1、長さは厳密な整数0〜99です。真偽値・小数・`null` は受け付けません。
入力は不変のコピーへ変換します。数字を丸なしの場所に置くと、この補助関数は拒否します。丸を暗黙に追加しません。
長さ1や、盤面で実現できない長さは、書式としては有効でも解なしになることがあります。端点には白い隣があるため、実際の長さは2以上です。
長さ0の丸は従来どおり数字なしの端点で、長さ0を要求する丸ではありません。

## 再現例を生成する

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-numbered-nurimisaki-recipe.json --selection finite --seed 0 --output numbered-nurimisaki.json --quiet
uv run --no-sync python examples/generate_shading.py show numbered-nurimisaki.json
uv run --no-sync python examples/generate_shading.py verify numbered-nurimisaki.json
uv run --no-sync python examples/generate_shading.py check numbered-nurimisaki.json --answer ".../##."
```

[2×3の例](../examples/shading-numbered-nurimisaki-recipe.json)は上のPython例と同じ5ルールです。
数字なしの同じ丸配置では3解ありましたが、左上3・右下2を固定すると一意になり、追加セルヒントは不要です。
左上からは横に3マス、右下からは縦に2マスが見えます。曲がった先までの道の全長ではありません。
数字と丸の配置はレシピの固定条件です。生成器はそれらを選択・削減せず、追加セルヒントを削減します。
`show` は丸の配置と可視数を別の格子に示します。完全解は通常表示で隠しますが、保存JSON自体には答えが入っています。

## Webと汎用の組合せ

Webでは「丸を白の端点と一致させる」と「数字から見える白マス数を固定」を選び、丸の位置と可視数を別々に入力します。
この例では、初期選択の黒数を外し、白連結と黒白それぞれの2×2禁止も選びます。
丸と可視数だけの表示では、端点上の数字を大きな丸の内側へ置きます。
同じセルに固定ラベル・面積など別の意味もある場合は、従来の位置を分けた表示を使い、読み上げにも各意味を含めます。

汎用の `ShadingRecipe`、保存ファイル、Webでは、丸なしの場所に独立した可視数を置く別の組合せも許します。
それはこの補助関数が検証する数字付きぬりみさきの配置とは区別してください。
保存されるのは既存の2ルールIDと格子であり、関数名・import先・任意コードではありません。新しいファイル形式は不要です。

## 検証と限界

テストでは2×3の全黒白盤面から端点と直線長を独立に求め、得られる各数字配置についてDSLの全回答と照合します。
参照実装は唯一の白い隣から方向を決め、その方向を変えずに歩きます。四方向の可視数の符号化とは分けています。
丸自身の数え落とし、曲がり、黒による遮断、盤端、数字なしの丸、入力と保存の互換性、生成から表示・解答確認までを検証します。
これらは有限の検証で、任意サイズの性能や任意の組合せの成立を保証しません。
既存の保存CLIは25セル、Web・有限診断は9セル上限です。Webは既存の計算予算を使い、通常CLIには壁時計の上限がありません。
端点・可視数の説明可能な推論手順は未対応と報告します。一意性から人間の難易度は判断しません。
