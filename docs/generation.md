# 生成レシピの契約

`generate()` と `reduce_clues()` は、3つの操作を持つクラスまたはオブジェクトを受け取ります。
`GeneratablePuzzle[P, C]` の `P` は具体的な `Puzzle` の型、`C` はヒントの型です。

| 操作 | 役割 |
| --- | --- |
| `create_empty() -> P` | ヒント以外の基礎ルールを持つ盤面を作る |
| `extract_clues(solution, puzzle: P) -> list[C]` | 完成した盤面から候補ヒントを抽出する |
| `build_from_clues(clues: list[C]) -> P` | 同じサイズ・基礎ルールでヒントを再適用する |

クラスメソッドを持つ `SudokuPuzzle` はそのまま渡せます。
サイズやルールを持つインスタンスを渡せば、生成器にパズル固有の分岐を足さずに
設定を引き回せます。実行可能な例は [compose_binary.py](../examples/compose_binary.py)です。

例えば Slitherlink のサイズを保持するレシピは次のように書けます。

```python
from dataclasses import dataclass
from puzzle import Solution
from puzzle_defs import SlitherlinkPuzzle
from puzzle_defs.puzzles.slitherlink import Clue

@dataclass(frozen=True)
class SlitherlinkRecipe:
    rows: int
    cols: int

    def create_empty(self) -> SlitherlinkPuzzle:
        return SlitherlinkPuzzle.create_empty(self.rows, self.cols)

    def extract_clues(self, solution: Solution, puzzle: SlitherlinkPuzzle) -> list[Clue]:
        return SlitherlinkPuzzle.extract_clues(solution, puzzle)

    def build_from_clues(self, clues: list[Clue]) -> SlitherlinkPuzzle:
        return SlitherlinkPuzzle.build_from_clues(clues, self.rows, self.cols)
```

Slitherlink の非空ループを一意性判定するには、別PRの
[回答変数に基づく一意性修正 (#2)](https://github.com/airtoxin/puzzle-box/pull/2)が必要です。
全ヒントを抽出しても必ず一意になるとは限らないため、生成の失敗も正常な結果として扱います。
空のループを禁止したい場合は、レシピが毎回作る基礎モデルに非空制約を入れてください。

## ヒントを減らす前提

ヒントを減らす操作は、制約だけを減らす必要があります。
盤面サイズ、ピースの集合、必須の木、解を区別する変数などを変えてはいけません。
この単調性の前提があると、一度削除できなかったヒントは後からも削除できません。
1回の巡回で「どの1つを消しても一意でなくなる」状態にできます。

全体で最も少ないヒント数を探索するアルゴリズムではありません。
また、ぬりかべの島の数字や Tents の木のように盤面構造を定義する情報は、
単純にこの削除候補へ入れず、固定するか別の生成戦略を使う必要があります。

## 失敗と重複

最初のヒント集合が解なし・複数解・一意性未証明の場合、`reduce_clues()` は
`ValueError` を返します。空リストも検証します。
`generate()` は基礎モデルが解けない場合 `RuntimeError`、抽出ヒントが一意でない場合
`ValueError` を返します。これは不正な問題を成功として返さないための契約です。

同じ値のヒントが2つあっても、削除は1つの出現単位で試します。
ヒントの同値判定や hash に依存せず、入力リストも変更しません。
基礎モデルにすでに一意な解があれば、結果のヒント数は0でも構いません。

`seed` はソルバーの乱数 seed と削除順に渡します。削除順は再現可能ですが、
CP-SAT の並列探索・バージョン差もあるため、生成盤面の完全な再現性や均一性を
保証するものではありません。結果を保存する際は盤面・ヒント・ルール・依存バージョンも残してください。

## 検証方法

数独の既存テストに加え、幅4〜6の二値盤面について、個数ルールと非接触ルールを
切り替えて生成します。CP-SAT を使わず `itertools.product` で全盤面を列挙する
検証器が、結果の一意性と各ヒントの必要性を確認します。
CLI例も実行し、出力されたヒントと回答を同じ独立した検証器で確認します。
