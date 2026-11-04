# 既知の制約部品を保存して再利用する

`examples/composed_shading_recipe.py` は、[既存レシピへの追加制約](recipe-constraint-composition.md)のうち、
標準では個数と連結という2種類の部品をJSONに保存します。部品の識別子・対象色・設定を明示して、読込時に
同じ `ConstrainedRecipe` を作り直します。任意のPython関数をシリアライズする形式ではありません。

## 保存から生成・再検証まで

同梱の[設定例](../examples/composed-shading-recipe-sample.json)は、2×3盤面で白が連結する既存レシピに、
「黒セルが2個」と「黒セルも連結する」という部品を追加します。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_composed_shading.py generate --recipe examples/composed-shading-recipe-sample.json --seed 0 --output composed-puzzle.json
uv run --no-sync python examples/generate_composed_shading.py verify composed-puzzle.json
```

出力先は新しいファイルを指定してください。既存ファイルや入力ファイルには上書きしません。
矛盾する部品やヒント不足で生成に失敗した場合も、問題ファイルは作成しません。
JSONには答えも含まれます。現在は生成・検証用であり、答えを隠す表示や解答入力のCLIはありません。

生成物は `puzzle-box/composed-shading-v1` 形式で、`recipe` に追加部品を含む設定全体、
`seed`、`clues`、`solution` を保存します。検証時は必ずそのレシピを再構築し、保存された答えと
唯一解の一致、各ヒントを一つ取り除くと一意でなくなることを確認します。
生成をやり直すには元のレシピファイルを再利用します。生成物の `recipe` を別のJSONへ取り出しても同じ設定を使えます。

## Pythonから部品を選ぶ

次のコードは、リポジトリの `examples` で実行するスクリプトを想定しています。

```python
import json
from pathlib import Path
from generator import with_constraints
from puzzle_defs import ConnectedWhite, ShadingRecipe
from composed_shading_recipe import CellCount, ConnectedCells, recipe_record, load_recipe

recipe = with_constraints(
    ShadingRecipe(2, 3, (ConnectedWhite(),)),
    CellCount("black", 2),
    ConnectedCells("black", nonempty=True),
)
with Path("my-recipe.json").open("x", encoding="utf-8") as stream:
    json.dump(recipe_record(recipe), stream, indent=2)
restored = load_recipe(Path("my-recipe.json"))
```

この2部品は既存DSLの個数制約と `connected` を使います。`ConnectedCells` は上下左右の接続を扱い、
斜めは接続と数えません。白を選ぶ場合は黒変数の否定を使い、回答の射影は黒白セルのままです。

| 保存するID | 必須設定 | 意味 |
| --- | --- | --- |
| `cell-count/v1` | `color`: `black` / `white`、`count`: 整数 | 指定色のセルがちょうど指定個数 |
| `connected-cells/v1` | `color`: `black` / `white`、`nonempty`: 真偽値 | 指定色が上下左右で連結。`false`ならその色が0個でも成立 |

レシピの形式は `puzzle-box/composed-shading-recipe-v1` です。`base` は既存の
[`puzzle-box/shading-recipe-v1`](shading-recipe-files.md)、`components` は上記の部品の配列です。
順序と重複を保存し、空配列は追加条件なしを意味します。基礎ルールを除去する指定はありません。

## 入力契約と互換性

- 9セル以下、追加部品8個以下、JSONはUTF-8で65,536バイト以下です。基礎ルールも既存形式の8個制限に従います。
- 必須フィールドと型を検査し、不明なフィールド・部品・形式・バージョンは拒否します。未知の部品を読み飛ばすと問題の意味が変わるためです。
- `count`・座標・seedに真偽値や小数は使えません。重複JSONキー、不正UTF-8やJSONもエラーです。
- `module`、関数名、コード文字列、pickleなどを読み込む経路はありません。JSONの値からimport・eval・任意関数呼び出しを行いません。
- Pythonから書き出す場合も、登録済みの部品と基礎レシピの**完全一致する型**だけを受理します。独自関数、未登録のサブクラス、ラッパーの入れ子は拒否し、未知の部品を実行して調査することもしません。
- 既存の黒白問題形式とは別形式です。元の黒白CLIへ渡すと拒否されます。`recipe.base` だけ保存したり、形式名だけ書き換えたりして追加条件を落とさないでください。

バージョンはデータ構造と部品の意味を識別します。既存IDの意味を変える拡張は、新しいIDまたは形式と
明示的な移行を必要とします。別ソルバー版を跨いだseed出力の一致は保証しません。`uv.lock`と同じ環境を使い、
読み込んだ問題の意味は `verify` で確認してください。seedは由来の記録で、唯一解の証拠ではありません。
検証は保存内容に対するもので、ファイルの作成者や改変の有無を認証するものでもありません。

## 対応範囲

標準の読込側は信頼する実装にあらかじめ含めた2部品に限定しています。新しいルールを保存したい場合は、
[信頼済みPython側の明示登録](custom-component-registration.md)で意味・対象・型・範囲を定義したIDを追加し、
独立した解集合と保存前後をテストする必要があります。
任意Pythonの自動登録、ループ辺・異種盤面、ヒントの自動導出、探索・説明推論への接続は未対応です。

小盤面制限は実行時間の保証ではありません。このCLIには実行時間の上限設定がなく、大きな探索には使いません。
一意性とヒントの既約性は、最少ヒント数、生成結果の均一な分布、人間にとっての解きやすさを意味しません。
