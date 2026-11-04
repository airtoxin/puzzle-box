# 探索したレシピを保存して生成する

黒白の探索で選んだルール・寸法・候補ヒント形式を、生成器へファイルで渡せます。
毎回引数を転記せず、同じ設定とseedで再実行できます。
対象は[保存形式に対応する組み込みルール](composable-shading.md)です。任意のDSLや他のパズル型の共通保存形式ではありません。

## 最短の例

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-recipe-sample.json --seed 6 --output puzzle.json
uv run --no-sync python examples/generate_shading.py verify puzzle.json
```

サンプルは3×3の「黒3個＋黒マス非隣接」で、候補ヒントにセル・行・列を指定しています。
Python 3.12.14 / OR-Tools 9.15.6755 でseed 6を使うと、行0の黒数1・行1の黒数2という
2個のヒントだけが残り、答えは `.#./#.#/...` になります。唯一解と各ヒントの必要性を検証できます。

`show puzzle.json` や `check puzzle.json --answer ...` で[表示・解答確認](play-shading.md)もできます。

## 探索から保存する

```sh
uv run --no-sync python examples/explore_shading.py --rows 3 --cols 3 --black-counts 3 --candidates count non-touching --hints cell row-count column-count --explain 1 2 --export-recipe chosen.json
uv run --no-sync python examples/generate_shading.py generate --recipe chosen.json --seed 6 --output puzzle.json
uv run --no-sync python examples/generate_shading.py verify puzzle.json
```

`--explain` の1始まりの候補番号が、表示と保存の両方の対象です。選択は必須で、
`--explain` に番号を付けなければルール0個を明示的に選びます。範囲外・重複番号は拒否します。
引数の番号順ではなく、元の候補順で保存します。同じ内容のルールが別の番号にあれば別の出現として残します。
候補ヒント形式の順序も保持します。自動的に冗長ルールを削除する処理はありません。

`--export-recipe` は設定だけを保存し、従来の `--output` は反例を含む探索レポートを保存します。
両方を使う場合は異なるファイルを指定してください。`--json` と `--explain` は引き続き併用できません。
レポート全体を生成器に読み込ませる機能はありません。

## ファイルの意味

```json
{
  "format": "puzzle-box/shading-recipe-v1",
  "rows": 3,
  "cols": 3,
  "rules": [
    {"type": "count", "count": 3},
    {"type": "non-touching", "diagonal": false}
  ],
  "clue_kinds": ["cell", "row-count", "column-count"]
}
```

| 形式 | 内容 | 読み込む操作 |
| --- | --- | --- |
| `shading-recipe-v1` | 寸法・ルール・候補ヒント形式。答えもヒント値も含まない。 | `generate --recipe FILE` |
| `shading-v1` / `shading-v2` | 生成された問題・答え・seed・環境情報。 | `verify FILE`、`show` / `check` |
| `shading-exploration-v1` | 全部分集合の比較結果・反例。 | 閲覧用。生成器への入力にはしない。 |

表の形式には共通して `puzzle-box/` の接頭辞があります。
レシピの5項目はすべて必須で、追加項目は認めません。保存後に手で編集することもできますが、
Pythonの式・クラス名・モジュールパスを実行する仕組みはありません。

- `rows` / `cols`: 正の整数、積が25以下。[固定成分サイズ](component-size.md)を含む場合は9以下です。小数・真偽値は整数として受け付けません。
- `rules`: 最大8出現。既知ルールのパラメータを厳密に検証します。黒数は盤面積以下です。部屋ルール同士は同じ分割を共有します。
- `clue_kinds`: `cell` / `row-count` / `column-count` の重複のない配列。空も有効ですが、一意な生成結果が得られる保証はありません。
- ファイル: UTF-8のJSON、最大65,536バイト。重複キー、NaN / Infinity、不正な型、未知のルールや項目は拒否します。

読込はソルバーを作る前に構造・値・サイズを検証します。探索の上限は従来どおり9マス・8候補出現です。
固定成分サイズを使わないレシピは25マスまで手で作って生成できますが、9マスを超える全列挙診断はできません。
これらのサイズ制限は求解時間の上限ではありません。

## 上書きとエラー

`--recipe` は `--rows`、`--cols`、`--rules`、`--hints`、`--black-count`、`--diagonal`、
`--allow-empty-white` と併用できません。同じ値を指定してもエラーです。
設定の変更はレシピを編集するか、別のレシピを保存して明示的に行います。
`--seed`、`--output`、`--quiet` は併用できます。

レシピの入力と問題の出力、レシピ出力とレポート出力を同じファイルにはできません。
解決済みパスや既存ファイルの別名でも検査します。通常の別の出力先は従来どおり上書きされます。
入力検証や生成が失敗した場合、問題出力は書き込みません。複数の出力への書込みは一括トランザクションではないため、
I/Oエラー時には片方の出力だけが保存される可能性があります。

| 状況 | 結果 |
| --- | --- |
| 不正な形式・入力・引数併用 | 理由を示して終了コード2。 |
| ルールが矛盾する | 完成解の生成失敗として終了コード2。レシピの保存自体は矛盾の解消を意味しない。 |
| 選んだ完成解を全候補ヒントでも一意にできない | 初期ヒントの一意性エラーで終了コード2。ヒント形式を変更せず、再試行もしない。 |
| 一意な完成解が得られ、削減も成功する | 従来の問題JSONを出力。`verify` で唯一解と既約性を再確認できる。 |

例えば2×2の「黒2個＋非隣接」を行・列ヒントだけで保存すると、2つの対角配置が同じ全ヒントになります。
どのseedでもこの組を区別できません。セルヒントを含める場合は、レシピの `clue_kinds` を自分で変更してください。
一部の完成解だけ識別できるレシピもあり、探索結果が「識別可能」を含むことだけで任意seedの成功を保証しません。

9セル以下の対応する組み込みルールでは、任意指定の `--selection finite` が識別可能な完成解を全列挙して選びます。
ルール・ヒント形式を保ったまま通常の削減器へ渡し、結果をDSLで検証します。
この指定は `--recipe`、`--seed`、`--output`、`--quiet` と併用できます。
`--quiet` は答えを含むJSONを画面へ出さずに保存します。
手順と適用範囲は [小盤面の候補選択](finite-shading-generation.md)を参照してください。
上表の「初期ヒントで一意にできない完成解を選ぶ」失敗は既定の `--selection solver` の動作です。

## 再現性と設計判断

seedは盤面のルールではなく生成時の条件なので、レシピには保存しません。省略時は既存どおり42です。
生成された問題には、従来どおりseed・Python・OR-Toolsのバージョン・seed指定時1 workerが記録されます。
レシピの配列順序を含めた設定とseed、ロック済み依存環境を一緒に保管してください。
同じ環境の別プロセスで `PYTHONHASHSEED` を変えても、サンプルの出力JSONが一致することを検証しています。
異なるソルバーバージョンやOSでのバイト一致、均一抽選は保証しません。

ルールの読み書きは `examples/shading_recipe.py` に共有し、生成済み問題のv1/v2形式は変更していません。
既存の引数による生成と同じseed・設定なら同じ出力になることも確認します。
Pythonから独自ルールを使う既存の `ShadingRecipe` は維持しますが、ファイル化は正確に既存4型だけです。
既存型のサブクラスも、追加の意味を失って保存しないよう拒否します。

この形式は「選択→保存→読込→生成→検証」を接続します。全パズルの共通レシピ、任意DSLの直列化、
ルール・ヒントの同時最適化、人間向け難易度、任意の設定での生成成功は保証しません。
