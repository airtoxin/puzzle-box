# 黒白ルール断片を組み合わせる

`ShadingRecipe` の同じ黒白セルへ、下表の6断片と[既定4断片](composable-shading.md)を追加できます。
各断片はヒントによらない基礎制約です。生成器はセル・行・列ヒントを削減し、黒白盤面を回答として唯一性を検査します。
これらはパズルの規則の一部であり、ぬりかべ・のりのり・LITS 全体の実装ではありません。

| Python / 保存・CLI・Web ID | 条件 | 境界・組合せの注意 |
| --- | --- | --- |
| `ConnectedBlack(nonempty=True)` / `connected-black` | 黒全体が上下左右でつながる | 既定で黒1個以上。`False` なら黒0個も許す。斜めだけではつながらない |
| `NoBlack2x2()` / `no-black-2x2` | 全黒の2×2窓を禁止 | 幅か高さが1なら制約なし |
| `BlackDominoes()` / `black-dominoes` | 黒の各連結成分がちょうど2マス | 黒0個・別成分の斜め接触を許す。部屋ごとの黒数は指定しない |
| `NoThreeConsecutive()` / `no-three-consecutive` | 各行・列の同色3連続を禁止 | 黒にも白にも適用。斜め・長さ2以下の行列には制限なし |
| `BalancedLines()` / `balanced-lines` | 各行・列で黒数と白数が等しい | 片方でも奇数寸法なら矛盾。切捨てや自動サイズ変更はしない |
| `DistinctLines()` / `distinct-lines` | 行同士・列同士がそれぞれ異なる配列 | 行と列の一致は許す。反転して同じ配列は、元の順序が違えば許す |

参照した規則は、[ニコリのぬりかべ](https://www.nikoli.co.jp/ja/puzzles/nurikabe/)と
[LITS](https://www.nikoli.co.jp/ja/puzzles/lits/)の黒連結・黒2×2禁止、
[のりのり](https://www.nikoli.co.jp/ja/puzzles/norinori/)の2マスの黒成分、
[Simon Tatham の Unruly](https://www.chiark.greenend.org.uk/~sgtatham/puzzles/doc/unruly.html)の
同色3連続禁止・行列の白黒同数と、任意設定の行列重複禁止です。
[Binary Puzzle の規則](https://www.binarypuzzle.com/rules.php)にも後者3条件が使われます。
ぬりかべの数字つき白領域、のりのりの「各部屋に黒2個」、LITSの部屋・テトロミノ・形の接触条件は、
この6断片に含みません。既存の専用パズルクラスの規則は変更しません。

## 保存レシピから試す

リポジトリのルートで実行します。既存ファイルを上書きしない出力先を選んでください。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-sea-recipe.json --selection finite --seed 0 --output sea.json --quiet
uv run --no-sync python examples/generate_shading.py show sea.json
uv run --no-sync python examples/generate_shading.py verify sea.json
```

- [黒連結＋黒2×2禁止＋黒4個](../examples/shading-sea-recipe.json)：2×3。黒2×2禁止により10通りから8通りに絞ります。数字つき白領域はありません。
- [黒2マス成分＋黒4個](../examples/shading-domino-recipe.json)：3×3。部屋はありません。
- [白黒同数＋同色3連続禁止＋行列重複禁止](../examples/shading-binary-recipe.json)：2×2。3連続禁止はこの寸法では冗長です。

上の `--recipe` を入れ替えて同じ手順を使えます。`show` は解を隠してルールと入力テンプレートを表示し、
`check` で回答を確認できます。詳細は[端末で解く](play-shading.md)を参照してください。
保存問題には解も含まれます。seed再現は同じソフトウェア環境内での約束で、環境をまたぐ一致は保証しません。

Pythonでは通常の `generate(recipe, seed=...)` にも渡せます。例えば4×4なら3連続禁止にも意味があります。
この呼出しには壁時計の時間制限がないので、大きな盤面へ無制限に拡大しないでください。
Webの小盤面生成には壁時計の予算がありますが、この4×4 Python例はWebの対象外です。

```python
from generator import generate
from puzzle_defs import BalancedLines, NoThreeConsecutive, DistinctLines, ShadingRecipe

recipe = ShadingRecipe(4, 4, (BalancedLines(), NoThreeConsecutive(), DistinctLines()))
clues = generate(recipe, seed=0)
puzzle = recipe.build_from_clues(clues)
```

## 矛盾・冗長性・ヒントを別々に調べる

```sh
uv run --no-sync python examples/analyze_shading.py --rows 2 --cols 3 --rules count black-dominoes non-touching --black-count 2
uv run --no-sync python examples/explore_shading.py --rows 2 --cols 3 --candidates black-dominoes connected-black no-black-2x2 --hints cell
uv run --no-sync python examples/analyze_shading.py --rows 2 --cols 2 --rules balanced-lines distinct-lines no-three-consecutive --hints row-count column-count
```

最初は「黒2個・黒2マス成分・黒非接触」が矛盾します。2つ目では、黒2マス成分だけで黒2×2禁止を満たすため、
後者は冗長です。さらに非空の黒連結を足すと、黒成分が1個になり、黒はちょうど2個になります。
最後は2通りの対角配置が同じ行・列数を持ち、個数ヒントだけでは識別できません。
`--hints cell row-count column-count` にすれば必要なセルヒントを残せます。
ルールだけの成立性、ヒントを含む唯一性、解きやすさは別の性質です。

## UI・安全性・対応範囲

[Webアプリ](web-app.md)の「黒白セル」では、追加6断片も定義の `RuleUi` から選択欄と説明を作ります。
すべて `rectangular-cells` 上の `answer/binary-cells` を共有するため、新しい描画器は不要です。
黒連結の `nonempty` だけが追加パラメータです。白黒同数を2×3で選ぶと、UIは描画可能でも生成結果は「矛盾」です。
9セル以下では白黒同数が成立する偶数寸法は2×2だけです。実用サイズの二値パズル全般をWebで生成できるとはしていません。
他の盤面プロフィールへこのIDを渡すことは拒否します。任意コードのimportやアップロードは行いません。

既定の生成4ルール・探索候補4ルールは変わりません。保存形式は同じ版に既知IDを追加しており、
旧版の読み手は未知IDを拒否します。厳密な型だけを保存し、サブクラスの独自制約を落として保存しません。
有限診断・選択生成は9セル・8ルール出現以下、Webは9セル・8種類以下、保存CLIは25セル以下です。
これらのサイズ制限は計算時間の保証ではありません。Webの壁時計予算と未確定結果の扱いは維持します。

有限検査器は制約の符号化を使わず、座標集合の連結成分、配列の比較、色の個数を検査します。
小盤面の全回答とDSLの可視解を照合しますが、任意サイズや任意の自作ルールを全検証したことにはなりません。
[説明推論](shading-deductions.md)は追加6断片に未対応で、そのルール番号を `rules_without_deductions` に残します。
対応済みのルール・ヒントによる推論だけを進め、未確定セルを答えから埋めません。唯一解は人間向け難易度を保証しません。
