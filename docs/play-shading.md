# 端末で生成したパズルを解いてみる

既存の CLI だけで問題の表示と解答確認ができます。ブラウザやサーバー、新しい依存パッケージは不要です。
リポジトリのルートで準備し、まず保存済みの例題を表示してください。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_shading.py show examples/shading-mixed-sample.json
```

この例のルールは「黒マスは3個」「黒マス同士は辺で接触しない」です。
表示は ASCII の英語表記で、端末の色や特殊なフォントを使いません。

```text
Shading puzzle: 3 rows x 4 columns

Rules:
- Exactly 3 cells are black.
- Black cells must not share an edge.

     column  1  2  3  4
      count  1  -  -  -
row count |
  1     2 |  ?  #  ?  ?
  2     1 |  ?  ?  ?  ?
  3     - |  ?  ?  ?  ?
```

`#` は黒、`.` は白、`?` は未確定です。上端の `count` は列の黒マス数、
左端の `count` は行の黒マス数です。`-` は個数ヒントがないことを表し、0とは異なります。
表示上の行・列番号は1始まりです。Python API と JSON の座標は従来どおり0始まりです。
盤面に表示する色は与えられたヒントだけで、推論で決まるマスも自動では埋めません。

## 完成した盤面を確認する

表示の末尾に `Answer template: ?#??/????/????` のような入力用テンプレートが出ます。
全ての `?` を `.` または `#` に置き換え、次の形式で渡します。

```text
uv run --no-sync python examples/generate_shading.py check FILE --answer "完成した各行を / で区切った文字列"
```

`FILE` は表示した JSON のパスです。各行は上から順番に、各マスは左から順番に入力します。
セルの間の空白は省略しても付けても構いません。`#` や空白をシェルが解釈しないよう、
解答全体を引用符で囲んでください。未完成の `?`、0/1、盤面と異なる寸法は入力エラーです。

正解なら `Correct. All rules and clues are satisfied.`、不正解なら
`Not correct. Check the rules and given clues.` と表示します。どちらも解そのものは表示しません。
元の JSON や入力した盤面を変更せず、正誤だけを返します。

<details>
<summary>例題の正解を使った実行例（解を表示します）</summary>

```sh
uv run --no-sync python examples/generate_shading.py check examples/shading-mixed-sample.json --answer ".#.#/#.../...."
```

この入力では `Correct. All rules and clues are satisfied.` と表示されます。

</details>

答えを盤面で見る場合だけ、明示的に `--solution` を付けます。

```sh
uv run --no-sync python examples/generate_shading.py show examples/shading-mixed-sample.json --solution
```

## 答えを見ずに新しい問題を作る

```sh
uv run --no-sync python examples/generate_shading.py generate --rows 3 --cols 4 --rules count non-touching --black-count 3 --hints cell row-count column-count --seed 0 --output puzzle.json --quiet
uv run --no-sync python examples/generate_shading.py show puzzle.json
```

`--quiet` は答え入りの JSON の標準出力を抑えます。保存先の `--output` が必須です。
既存の生成コマンドは、`--quiet` を省略すれば従来どおり JSON を出力します。
JSON ファイル自体には引き続き解が含まれるため、解く前に中身を開くと答えが見えます。

## 検証と制約

`show` / `check` は v1・v2 の保存物を受け付けます。先に既存の `verify` と同じ検証を行い、
問題が一意、保存解が正しい、各ヒントが必要であることを確認します。
改変した保存解を入力しても正解とは扱いません。検証した唯一解と完成盤面を照合する設計です。
曖昧な問題、壊れた保存解、冗長なヒントを持つ手書きのデータは表示・照合の対象外です。

`check` の終了コードは、正解が0、不正解が1、入力・ファイルの検証エラーが2です。
`show` と `generate` は成功時0、入力・検証エラー時2です。
未完成盤面の部分確認、誤ったマスの指摘、解き筋の説明、編集画面、進捗の保存はありません。
CLI の25マス制限を維持しています。毎回求解して検証するため、即時応答や時間上限は保証しません。

テストでは v1/v2 の表示、ヒント以外を隠すこと、明示的な解の表示、0とヒントなしの区別、
2桁の個数、ルールのオプション表記、終了コード、保存解の改変拒否、元ファイルの不変性を確認します。
2×2の全16盤面について独立したルール判定と照合し、生成→表示→解答確認も実行します。

この実装は [PR #10](https://github.com/airtoxin/puzzle-box/pull/10) の混合ヒントを土台に追加しました。
#9 の黒白合成と、main 採用済み #2〜#8 の求解・生成基盤も使います。
新しい技術基盤や公開は追加していません。現在の base・レビュー・採用状況は
[PR #11](https://github.com/airtoxin/puzzle-box/pull/11) とレビューガイドを参照してください。
