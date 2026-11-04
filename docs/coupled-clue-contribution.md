# 異種合成で全候補ヒントと残ったヒントを比較する

全候補ヒントがあるときに不要な規則でも、実際に残ったヒントでは必要になることがあります。
この例では、2×4・矢印なし・全白の外周ループを対象に、[異種探索](coupled-rule-exploration.md)と同じ
3規則・黒セルと辺の共同回答を使います。通常のヤジリンから規則を外した構成は、標準ヤジリンとは区別してください。

候補は黒白8個と辺10個、計18ヒントです。下表では元の答えを固定し、示したヒントだけを残します。

| 規則 | 固定する残りヒント | 規則を1つ外したときの解数 |
| --- | --- | --- |
| 結合のみ（mask 1） | 内部の縦辺 `(0,1)-(1,1)` と `(0,2)-(1,2)` を使わない | 結合を外すと256解 |
| 結合＋非隣接（mask 3） | `(0,2)-(1,2)` を使わない | 結合を外すと123解、非隣接を外すと3解 |
| 3規則すべて（mask 7） | 0ヒント | 結合を外すと246解、非隣接を外すと6解、単一サイクルを外すと2解 |

元の18ヒントをすべて固定すると、各規則を外しても元の答えだけが残ります。
比較には常に**同じ元のヒント値**を使い、別解から新しいヒントを作り直しません。
各行の元の規則と残りヒントでは一意です。この例は1つの完成解と固定したヒント集合の性質で、
別の盤面・最少ヒント数・難易度・個別に不要な規則の一括削除についての証明ではありません。

## 123解と3解を再現する

リポジトリのルートで、依存環境を準備してから実行します。

```python
import sys
sys.path.insert(0, "examples")
from coupled_oracle import accepts, universe
from explore_coupled import CoupledModel, model_answers
from puzzle import Edge, Vertex
from puzzle_defs import YajilinRecipe

recipe = YajilinRecipe(2, 4, ())
edge = Edge(Vertex(0, 2), Vertex(1, 2))
space = universe(recipe)
for mask, count in [(3, 1), (2, 123), (1, 3)]:
    expected = {a for a in space if accepts(recipe, mask, a) and edge not in a.loop_edges}
    model = CoupledModel(recipe, mask)
    model.add(model.edge_on[edge] == 0)
    actual, _ = model_answers(model)
    assert actual == expected and len(actual) == count
    print(mask, count)
```

独立した有限列挙とDSL/CP-SATの全解集合を、黒白と辺の両方に射影して照合します。
CP-SAT列挙が時間内に完了しない場合はエラーとなり、未完了の集合を一致と認定しません。
探索は最大8セル・10辺で、各モデルの照合上限は既定10秒です。全処理の時間上限ではありません。
このコードは固定した小盤面の検証例で、任意DSLの保存・生成APIやヒントの自動最小化ではありません。
