# Puzzle Box

ペンシルパズルのルールを小さな制約に分け、組み合わせて解く Python DSL です。
CP-SAT を共通の求解基盤とし、セルの値・領域・ループ・対応付けを表現します。
問題生成器は、完成解からヒントを作り、一意性を保ちながら減らします。

プログラムから定義するライブラリに加え、[黒白10ルール](docs/shading-fragments.md)、[部屋・行列の4ルール](docs/room-fragments.md)、[成分の形の2ルール](docs/component-shapes.md)、[固定数字のルール](docs/number-fragments.md)、スリザーリンクの条件、黒白とセル中心ループの固定3条件を画面で扱う
[ローカル Web アプリ](docs/web-app.md)があります。任意のルール全般や盤面型を扱うアプリ、
良問の保証、人間向けの一般的な解法・難易度判定はまだありません。

## 試す

[Webデモをブラウザで開く](https://puzzle-box-five.vercel.app)。黒白・スリザーリンク・黒白とループの小盤面を生成できます。公開デモの計算予算は1回10秒までです。

Web アプリは `uv sync --all-packages --group dev --locked` の後、
`uv run --no-sync python examples/web_server.py` で起動し、`http://127.0.0.1:8765` を開きます。
ルール定義に宣言したパラメータと UI 要求から、設定欄・盤面・ヒント表示を構成します。
このローカルサーバーを外部公開する構成ではありません。Vercel用には別の[配信手順と計算制限](docs/deploy-vercel.md)があります。
対応範囲と設計は [Web アプリの使い方](docs/web-app.md)を参照してください。

Python 3.12 以上と [uv](https://docs.astral.sh/uv/) を使います。
リポジトリのルートで全 workspace package をインストールしてください。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/generate_shading.py show examples/shading-mixed-sample.json
```

保存済みの例題を、ルール・盤面・ヒント付きで表示します。通常は解を表示しません。
表示されたテンプレートを埋めて `check` で確認できます。手順は [端末で解いてみる](docs/play-shading.md)を参照してください。

新しく生成する場合は、`--quiet` を付けると答えを含む JSON を画面へ出さずに保存できます。

```sh
uv run --no-sync python examples/generate_shading.py generate --seed 17 --output shading.json --quiet
uv run --no-sync python examples/generate_shading.py show shading.json
uv run --no-sync python examples/generate_shading.py verify shading.json
```

3×3 の黒白盤面で「黒は3個・黒は辺接触しない・白は連結・白い2×2は禁止」を
組み合わせ、一意になるヒントと解を JSON で保存します。`--rules` で部品を選べます。
盤面サイズ・基礎ルールは固定され、ヒントを消しても変わりません。
実際の盤面、Python API、再現性の範囲は [ルール合成の実例](docs/composable-shading.md)を参照してください。
最初の1次元の例 [compose_binary.py](examples/compose_binary.py)も残しています。

セルの色に行・列の黒マス数ヒントを混ぜることもできます。

```sh
uv run --no-sync python examples/generate_shading.py generate --rows 3 --cols 4 --rules count non-touching --black-count 3 --hints cell row-count column-count --seed 0 --output mixed.json --quiet
uv run --no-sync python examples/generate_shading.py show mixed.json
uv run --no-sync python examples/generate_shading.py verify mixed.json
```

個数だけでは曖昧な場合も、必要なセルヒントを残します。
例題と成立条件は [複数のヒント形式](docs/mixed-shading-clues.md)にまとめています。

既存の数独生成は次の通りです。

```python
from generator import generate
from puzzle import unique
from puzzle_defs import SudokuPuzzle

clues = generate(SudokuPuzzle, seed=42)
puzzle = SudokuPuzzle.build_from_clues(clues)
puzzle.add(unique())
solution = puzzle.solve()
assert solution is not None
print(puzzle.result(solution))
```

## 構成

| パッケージ | 役割 | 主な入口 |
| --- | --- | --- |
| `puzzle` | グリッド、式、制約、CP-SAT 変換、求解 | `Puzzle`, `square_grid`, `connected`, `single_cycle` |
| `puzzle-defs` | パズル定義と領域・配置の列挙 | 既存8種類と `ShadingRecipe` による合成 |
| `solvers` | 入力から結果までの薄い関数 API | 各モジュールの `solve` |
| `generator` | ヒント抽出と一意性を保つ削減 | `generate`, `reduce_clues`, `GeneratablePuzzle` |

構造の詳細は [ARCHITECTURE.md](ARCHITECTURE.md)、
ルール・ヒント・回答の接続は [合成の設計](docs/composition-design.md)、
生成器の契約と使い方は [生成レシピ](docs/generation.md)を参照してください。

## ルールとヒントの組合せを診断する

9マス以下の黒白レシピでは、全配置を調べてルールの矛盾とヒント形式の不足を区別できます。

```sh
uv run --no-sync python examples/analyze_shading.py --seed-count 8
```

[小盤面の診断](docs/shading-diagnostics.md)に、同じ行列ヒントを持つ2つの答え、
矛盾するルール集合、seedを変えたときの完成解の多様性をまとめています。

候補ルールの全部分集合を比較する探索例もあります。

```sh
uv run --no-sync python examples/explore_shading.py
uv run --no-sync python examples/explore_shading.py --rows 3 --cols 3 --black-counts 3 --candidates count non-touching --explain 1 2
```

[組合せの探索](docs/shading-exploration.md)では、完成解集合を変えないルールと、
全候補ヒントがある場合の冗長性を分け、ルールを外すと唯一解を失う反例を表示します。

## レシピを保存して生成する

探索で選んだ設定を保存し、同じレシピから生成できます。

```sh
uv run --no-sync python examples/explore_shading.py --rows 3 --cols 3 --black-counts 3 --candidates count non-touching --hints cell row-count column-count --explain 1 2 --export-recipe chosen.json
uv run --no-sync python examples/generate_shading.py generate --recipe chosen.json --seed 6 --output puzzle.json --quiet
uv run --no-sync python examples/generate_shading.py show puzzle.json
uv run --no-sync python examples/generate_shading.py verify puzzle.json
```

設定・問題・探索レポートの区別、入力検証、再現性は [レシピの保存と読込](docs/shading-recipe-files.md) を参照してください。

探索で出題可能な完成解が見つかっても、通常生成が曖昧な別の完成解を選ぶことがあります。
対応する黒白の組み込みルール・9セル以下なら `generate --selection finite` で、一意に出題できる候補を先に列挙して選べます。
[選定から生成・表示・検証までの実例](docs/finite-shading-generation.md)に、行ヒントだけで出題する手順と限界をまとめています。

[複数の生成結果を比較する](docs/compare-shading-seeds.md)では、３つの保存済みレシピを使い、
残ったヒントで各ルールが必要かを比べて、選んだ問題を保存できます。

## 保存した問題でルールを診断する

生成された問題で、実際に残ったヒントに対するルールの必要性を診断できます。

```sh
uv run --no-sync python examples/diagnose_shading_rules.py puzzle.json --output rule-report.json
```

[保存ヒントでのルール診断](docs/stored-clue-rule-diagnostics.md)では、全候補ヒントとの違い、
別解の盤面、個別の冗長性から一括削除できない理由を説明しています。レポートは答えも表示します。

[推論の根拠を説明する](docs/shading-deductions.md)では、唯一解の確認と推論による解決を分け、
各手順の根拠を表示します。対応する手順で進まない場合は、未知のマスを残して未解決と報告します。

## 開発と検証

```sh
uv run --no-sync python -m pytest -q
uv run --no-sync pyright
uv build --all-packages --no-sources
```

テスト名は `*-test.py` です。Pyright はルートの `.venv` を使います。
CI は Ubuntu / Windows、Python 3.12 / 3.13 で同じテスト・型検査・ビルドを実行します。
依存更新時は `uv.lock` をレビューし、上記の検証も実施してください。

生成結果は一意性と1ヒントずつの削除に対する既約性を確認します。
最少ヒント数、均一なランダム分布、人間にとっての面白さは保証しません。
機能ごとの仕様・実行手順・制限は [ドキュメント一覧](docs/README.md)から参照できます。

## 辺に描くループでも試す

黒白とは異なる回答空間の実例として、スリザーリンク形式でも同じ生成器を使えます。
非空の単一ループに長さ指定・マス周囲の辺数・辺の使用状態を組み合わせます。

```sh
uv run --no-sync python examples/generate_slitherlink.py generate --loop-length 8 --seed 2 --output loop.json --quiet
uv run --no-sync python examples/generate_slitherlink.py show loop.json
uv run --no-sync python examples/generate_slitherlink.py verify loop.json
```

数字だけでは2解になる反例、API、合成できる範囲と未対応の接続は
[ループのレシピ](docs/slitherlink-composition.md)を参照してください。
表示したテンプレートから完成した辺を入力し、[解答の正誤確認](docs/play-slitherlink.md)もできます。

## 黒マスとループを同時に生成する

ヤジリンの「黒なら辺0本、白なら辺2本」という接続条件を使い、黒白セルとループ辺を
1つの回答として生成・検証する例もあります。

```sh
uv run --no-sync python examples/generate_yajilin.py show examples/yajilin-sample.json
uv run --no-sync python examples/generate_yajilin.py verify examples/yajilin-sample.json
```

[異種合成の例](docs/yajilin-composition.md)に、生成方法、数字を消しても残す矢印マス、
黒白が同じでも2種類のループになる反例、合成の限界をまとめています。
生成した問題はヒントだけを表示し、[黒マスと線を入力して正誤確認](docs/play-yajilin.md)できます。
