# Puzzle Box

ペンシルパズルのルールを小さな制約に分け、組み合わせて解く Python DSL です。
CP-SAT を共通の求解基盤とし、セルの値・領域・ループ・対応付けを表現します。
問題生成器は、完成解からヒントを作り、一意性を保ちながら減らします。

現在はプログラムから定義するライブラリです。任意のルールを画面で選んで
良問を自動生成するアプリや、人間向けの解法・難易度判定はまだありません。

## 試す

Python 3.12 以上と [uv](https://docs.astral.sh/uv/) を使います。
リポジトリのルートで全 workspace package をインストールしてください。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/compose_binary.py --width 6 --count 2
uv run --no-sync python examples/compose_binary.py --width 6 --count 2 --allow-touch
```

この小さな例は「黒マスは2個」と「黒マス同士が接触しない」を組み合わせ、
一意になるヒントと解を JSON で出力します。`--allow-touch` で後者だけを外せます。
盤面サイズ・基礎ルールはレシピに固定され、ヒントを消しても変わりません。

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
| `puzzle-defs` | パズル定義と領域・配置の列挙 | `SudokuPuzzle` など8種類 |
| `solvers` | 入力から結果までの薄い関数 API | 各モジュールの `solve` |
| `generator` | ヒント抽出と一意性を保つ削減 | `generate`, `reduce_clues`, `GeneratablePuzzle` |

構造の詳細は [ARCHITECTURE.md](ARCHITECTURE.md)、
実装調査・課題・発展案は [プロジェクトレビュー](docs/project-review.md)、
生成器の契約と使い方は [生成レシピ](docs/generation.md)を参照してください。

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
現状と修正中の既知の制限はプロジェクトレビューに整理しています。
