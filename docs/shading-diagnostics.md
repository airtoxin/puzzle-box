# 小盤面で「なぜ生成できないか」を調べる

`examples/analyze_shading.py` は、対応する組み込みルールを組み合わせた黒白レシピの診断例です。
**9マス以下の全黒白配置を調べ、完成解の有無と、希望するヒント形式が答えを区別できるかを分けます。**
必要に応じて、指定したseedでどの完成解が選ばれるかも観測します。生成器や求解APIは変更していません。

## 同じヒントになる2つの答え

ルートで `uv sync --all-packages --group dev --locked` を実行してから試せます。

```sh
uv run --no-sync python examples/analyze_shading.py
```

既定は2×2、黒マス2個、黒の縦横非隣接、行・列の黒マス数ヒントです。
16配置をすべて調べると、完成解は次の2つだけです。

```text
.#    #.
#.    .#
```

どちらも全行・全列の黒マス数が1で、**すべての候補ヒントを残しても区別できません**。
このレシピではseedを何回変えても、行・列ヒントだけで唯一解にはできません。
診断は `hint_policy: none_identifiable` と、共通ヒント・2つの答えを表示します。

```sh
uv run --no-sync python examples/analyze_shading.py --hints cell row-count column-count
```

セルヒントも候補に加えると2つとも区別できます。診断の段階ではヒントを追加・削除せず、
指定した候補集合の能力を調べるだけです。
実際の生成は同じ設定で `examples/generate_shading.py generate` を使います。

## ルールの矛盾と、成立するが一部しか区別できない場合

```sh
# 斜めの黒マス隣接も禁止すると、2×2に黒2個を置けなくなる
uv run --no-sync python examples/analyze_shading.py --diagonal

# 非隣接ルールを外すと完成解6個のうち4個は行・列ヒントで区別できる
uv run --no-sync python examples/analyze_shading.py --rules count

# 3ルールが一緒に矛盾する例
uv run --no-sync python examples/analyze_shading.py --rows 3 --cols 3 --black-count 5 --rules count non-touching connected-white no-white-2x2
```

最後の例では `count=5`、`non-touching`、`connected-white` の3つが矛盾します。
`no-white-2x2` を外しても矛盾は残ります。矛盾する3ルールの部分集合から1つを外すと成立します。

`minimal_conflicts` は**包含関係で最小の矛盾部分集合をすべて**返します。
ルール番号は表示順の1始まりで、同じルールが複数回あれば別の番号として扱います。
「元の全ルールから番号を1つ消せば必ず直る」「最少個数のルールを捨てる修正案」とは限りません。
複数の矛盾部分集合が同時に存在することもあるためです。

## 完成解の多様性は、seedの数とは別に数える

```sh
uv run --no-sync python examples/analyze_shading.py --seed-start 0 --seed-count 8
uv run --no-sync python examples/analyze_shading.py --rows 3 --cols 3 --black-count 3 --rules count non-touching connected-white no-white-2x2 --hints cell --seed-count 8 --json --output analysis.json
```

seed観測は、既存の `create_empty().solve(seed=...)` を使い、完成した黒白盤面と抽出ヒントを
有限検査器の結果と照合します。solverやヒント抽出が食い違うときは、診断結果として扱わずエラーにします。
同じ答えを返したseedには同じ `answer_id` を付けます。回転・反転した盤面は別の答えとして数えます。

Windows / Python 3.12.14 / OR-Tools 9.15.6755、seed 0〜7で次を観測しました。

| レシピ | 全完成解 | 全候補ヒントで区別できる完成解 | 8 seedで観測した異なる完成解 |
|---|---:|---:|---:|
| 2×2、黒2、縦横非隣接、行列ヒント | 2 | 0 | 1 |
| 同じルール、セル＋行列ヒント | 2 | 2 | 1 |
| 2×2、黒2だけ、行列ヒント | 6 | 4 | 1 |
| 2×2、黒2、斜めも非隣接 | 0 | 0 | 観測を省略 |
| 3×3、黒5、縦横非隣接、白連結、白2×2禁止 | 0 | 0 | 観測を省略 |
| 3×3、黒3、縦横非隣接、白連結、白2×2禁止、セルヒント | 4 | 4 | 1 |

**8つのseedが8種類の答えを選ぶとは限りません。** 一方、全完成解の個数とヒントの識別能力は
全列挙の結果なので、観測したseedに依存しません。
seed観測は有限の実測で、成功確率・均一抽選・人間にとっての多様性や難易度の評価ではありません。
ヒント削減後の問題の違いも数えていません。同じ答えから異なるヒント集合が生成される場合があります。

## 出力の読み方

| `hint_policy` | 意味と次の判断 |
|---|---|
| `no_completion` | ルールに矛盾がある。seedやヒントの変更では直らない |
| `none_identifiable` | 完成解はあるが、希望した全候補ヒントで区別できる答えがない。ヒント形式かルールを変える |
| `some_identifiable` | 区別できる完成解とできない完成解がある。別のseedを試す余地はあるが成功保証はない |
| `all_identifiable` | 全完成解が全候補ヒントで区別できる。ヒント削減前の一意性を満たせる |

通常は説明文、`--json` は機械可読の全結果を出力します。
`--output FILE` はJSONを保存します。共通ヒントの反例やseedで得た答えも含みます。
ルールの矛盾・ヒントの曖昧さは診断結果なので終了コード0です。不正な入力や検査器との不一致は2です。
`--rules`、`--hints` の後を空にすると、追加ルールなし・候補ヒントなしも調べられます。

## 検証範囲・設計上の限界

- 対象は既定4種類、[追加6断片](shading-fragments.md)、[部屋・行列の4断片](room-fragments.md)、[成分の形の2断片](component-shapes.md)、[固定数字の断片](number-fragments.md)の厳密な組み込み型だけです。
  任意のDSLルールや、既存型を継承したクラスは受け付けません。
- この例は17ルールと3ヒント形式の意味を有限検査器として別に記述しています。
  ルールを変更・追加する場合は検査器も更新する必要があります。汎用的なDSL解釈器とはしていません。
- 全列挙とヒントの分類は最大512盤面、矛盾集合は最大8ルール出現、seed観測は最大32回に限定します。
  盤面上限・試行数上限は求解時間上限ではありません。
- テストでは実際のDSLが返す全回答、固定した全盤面からのヒント抽出、矛盾部分集合とその削除、
  seed再現性、検査器との不一致、不正入力を確認しています。既存の生成・ヒント削減の挙動は変えません。
- Python・OR-Tools・OSを変えたときのseed観測結果の一致は保証しません。環境情報をJSONに保存します。

診断には黒白レシピと混合ヒントの意味を使います。ループ・領域パズルは対象外です。
黒白セルとループ辺を組み合わせた小盤面には、別の[異種合成の探索](coupled-rule-exploration.md)を使います。
