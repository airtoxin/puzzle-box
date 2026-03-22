# Puzzle Box Architecture

## このシステムは何か

パズルのルールを宣言的に記述して解を求めるための Python DSL とソルバー集です。
内部で CP-SAT (Google OR-Tools) を使いますが、利用者はそれを意識しません。

---

## 概念の全体像

### 登場する概念

```
┌─────────────────────────────────────────────────────────┐
│                     Puzzle (パズル)                       │
│  「解くべき問題」。変数・制約・feature を束ねる器          │
│                                                         │
│   ┌──────────┐   ┌──────────┐   ┌──────────────────┐   │
│   │ 変数     │   │ 制約     │   │ Feature          │   │
│   │          │──▶│          │◀──│ (制約の前提条件)  │   │
│   └──────────┘   └──────────┘   └──────────────────┘   │
│        ▲                                                │
│        │                                                │
│   ┌──────────┐                                          │
│   │ グリッド  │  空間構造 (セル・辺・頂点)                │
│   └──────────┘                                          │
│        ▲                                                │
│        │                                                │
│   ┌──────────────────┐                                  │
│   │ 列挙 / フィルタ   │  候補の事前計算                  │
│   │ (前処理)          │                                  │
│   └──────────────────┘                                  │
└─────────────────────────────────────────────────────────┘
        │
        ▼
  ┌──────────┐
  │ Solution │  求解結果
  └──────────┘
```

### 概念間の関係

**グリッド** はパズルの空間を定義します。セル・辺・頂点の3要素とその接続関係を持ちます。

**変数** はグリッド上の「決めるべきもの」です。各セルの値、各辺のオン/オフ、各配置を使うかどうか、など。変数はグリッド要素に紐付けて生成されます。

**制約** はパズルのルールです。変数に対して「この条件を満たせ」と宣言します。制約は変数を参照しますが、変数は制約を知りません。

**Feature** は制約の前提条件です。「この制約を使うにはセル変数が必要」「領域分割が必要」といった依存関係を表現します。Puzzle が feature を追跡し、制約追加時に検証します。

**列挙/フィルタ** は制約の材料を作る前処理です。「盤面に置ける全配置」「条件を満たす全矩形」などを事前に計算し、変数や制約の定義に使います。

**Puzzle** がこれらすべてを束ね、**Solution** を返します。

### データの流れ

```
グリッド定義 → 変数定義 → 制約追加 → 求解 → Solution
     │            │           │
     │            │      Feature 検証
     │            │
     └── 列挙/フィルタ ──┘
         (候補生成)    (変数の定義域を決める)
```

パズルを解くとは、この流れに沿って:
1. 空間を決め (グリッド)
2. 何を決めるか定め (変数)
3. どんなルールがあるか書き (制約)
4. CP-SAT に任せる (求解)

ということです。

---

## パズルの5つの構造パターン

実装済みのパズルは、変数と制約の組み合わせで5つのパターンに分類できます。

```
パターン A: セル値型         各セルに値を割り当て → 値の関係を制約
            (数独)           int_var_grid → all_different

パターン B: 辺ループ型       辺のオン/オフを決定 → ループ構造を制約
            (スリザーリンク)  bool_var_map(edges) → single_cycle

パターン C: セル所有者型     各セルの所属を決定 → 領域の性質を制約
            (ぬりかべ)       int_var_map(owner) → connected + count_eq

パターン D: 配置選択型       どの配置を使うか選択 → 全セル被覆を制約
            (タイリング,     列挙 → bool_var_map(placements) → exactly_one
             四角に切れ)

パターン E: 複合型           複数の変数系を連携
            (ヤジリン)       is_black + edge_on → sum_expr でリンク
```

各パターンは独立ではなく、組み合わせて使います。例えばヤジリンは A + B の複合です。

---

## 概念の詳細

### グリッド (`grid.py`)

パズルの空間構造。3つの幾何要素と、それらの関係を提供します。

```
Cell (マス目)                Vertex (格子点)              Edge (辺)
  セルの集まりが盤面            セルの角にある点             2つの頂点を結ぶ線分
  (0,0)(0,1)(0,2)...          格子点の数 =                辺の数 =
  パズルの基本単位              (rows+1) × (cols+1)        横辺 + 縦辺
```

これら3要素は `SquareGrid` を通じて相互に参照できます:

| 操作 | 意味 |
|------|------|
| `edges_around(cell)` | セルを囲む4辺を返す |
| `edges_incident(vertex)` | 頂点に接する辺を返す |
| `cells_sharing_edge(edge)` | 辺で隔てられた2セルを返す |
| `neighbors(cell)` | 直交隣接するセルを返す |

また、セルのグループ化ビューも提供します:

| ビュー | 重複 | 用途例 |
|--------|------|--------|
| `rows()` / `cols()` | なし | 数独の行列制約 |
| `blocks(h, w)` | なし | 数独の3×3ボックス |
| `windows(h, w)` | あり | ぬりかべの2×2プール禁止 |

---

### 変数と式 (`expr.py`)

「決めるべきもの」を表現します。CP-SAT の変数をラップし、ortools を隠蔽します。

#### 型階層

```
Expr                  比較演算子 → LinearConstraint を返す
 ├── Var              比較演算子 → BoolExpr を返す (reification)
 └── BoolExpr         制約としても 0/1 式としても使える
```

`Expr` は式の基底クラスです。`sum_expr()` の結果もこの型です。
`Var` は決定変数で、`==` が `BoolExpr` を返す点が特別です。
`BoolExpr` は「条件の成否」を 0/1 値として扱えるようにする仕組み (reification) です。

#### BoolExpr が DSL の要

`Var` の `==` / `!=` は `BoolExpr` を返します。`BoolExpr` は3つの文脈で使えます:

```python
owner[c] == 0                                # → BoolExpr を生成

p.add(owner[c] == 0)                         # 制約として: 値を強制
sum_expr(owner[c] == 0 for c in cells)       # 式として: カウント
connected(predicate=lambda c: owner[c] == 0) # 述語として: 活性判定
```

この統一的な仕組みにより、ぬりかべの「黒マスの連結性」「島のサイズ」「2×2禁止」をすべて同じ `owner[c] == value` で書けます。

#### 変数コンテナ

| 型 | キー | 生成 | 用途例 |
|----|------|------|--------|
| `VarGrid` | `Cell` | `int_var_grid()` | 数独のセル値 |
| `VarMap` | 任意 `Hashable` | `int_var_map()` / `bool_var_map()` | 所有者、辺、配置 |

---

### 制約

パズルのルールを表現するオブジェクト。`Puzzle.add()` に渡して登録します。

#### 3つのカテゴリ

**値制約** — 変数の値に関する条件

| 制約 | 意味 | 例 |
|------|------|---|
| `LinearConstraint` | 線形な比較 | `sum_expr(...) <= 3` |
| `BoolExpr` | reified 等式 | `owner[c] == 5` |
| `AllDifferentConstraint` | 全変数が異なる | `all_different(row)` |
| `OneOfConstraint` | ちょうど1つ成立 | `one_of(deg == 0, deg == 2)` |
| `UniqueConstraint` | 解が唯一 | `unique()` |

集約ヘルパー: `sum_expr`, `count_eq`, `exactly_one`

**位相制約** — グラフ構造に関する条件

| 制約 | 意味 | CP-SAT 実装 |
|------|------|------------|
| `SingleCycleConstraint` | 辺が単一閉路を形成 | `add_circuit` (有向アーク + セルフループ) |
| `ConnectedConstraint` | 活性セルが連結 | スパニングツリー (親ポインタ + 順序変数) |

**領域制約** — 領域分割に関する条件

| 制約 | 意味 |
|------|------|
| `same_shape_across(edge)` | 辺の両側の領域が同じ形状 (`=`) |
| `different_shape_across(edge)` | 辺の両側の領域が異なる形状 (`!`) |
| `all_adjacent_different_shape()` | 隣接する全領域が異なる形状 |
| `no_boundary_cross()` | 内部頂点で境界が十字交差しない (畳張り) |

---

### Feature (`features.py`)

制約には前提条件があります。Feature はその依存関係を明示し、不足時にエラーを出します。

| Feature | 意味 | 自動登録される操作 |
|---------|------|--------------------|
| `cell_vars` | セル上に変数がある | `int_var_grid()`, `int_var_map()` |
| `edge_vars` | 辺上に変数がある | `bool_var_map()` |
| `region_partition` | セルが領域に分割される | `add_feature()` で手動登録 |
| `shape_class` | 各領域に形状名がある | `add_feature()` で手動登録 |

各制約が require する feature:

```
all_different        → cell_vars
connected            → cell_vars
single_cycle         → edge_vars
same/different_shape → region_partition + shape_class
no_boundary_cross    → region_partition
```

不足時のエラー:
```
ShapeAcrossConstraint cannot be used here.

Missing features:
  - region_partition: cells are partitioned into non-overlapping regions

Hint:
  Define a region partition via placement-based exact cover.
```

---

### 列挙とフィルタリング (`polyomino.py`, `shikaku.py`, `regions.py`)

CP-SAT に渡す前に候補を事前計算する前処理です。「何が置けるか」を列挙し、「条件に合うもの」をフィルタします。

#### 列挙

| 関数 | 何を列挙するか | 候補の型 |
|------|---------------|---------|
| `enumerate_placements(board, piece)` | ピースの全配置 | `Placement` |
| `enumerate_shikaku_rectangles(board, clues)` | ヒント付き矩形 | `ShikakuRect` |
| `enumerate_connected_regions(board, size)` | 固定サイズの連結領域 | `Region` |
| `enumerate_rectangles(board, size)` | 軸平行矩形 | `Region` |

#### フィルタ

列挙結果をパイプライン的に絞り込みます:

```python
regions = enumerate_connected_regions(board, size=4)
regions = filter_number_equals_area(regions, numbers)    # 数字=面積
regions = filter_same_number_combination(regions, numbers, n)  # 同じ数字組合せ
```

| フィルタ | 条件 |
|---------|------|
| `filter_one_number_per_region` | 領域に数字が1つだけ |
| `filter_number_equals_area` | 数字 = 領域の面積 |
| `filter_same_number_combination` | 全領域が同じ数字の multiset |

#### 候補型の関係

```
Region(cells, clue_cell?)      汎用領域
Placement(piece_name, cells)   名前付き領域 (ポリオミノ)
ShikakuRect(clue_cell, cells)  ヒント付き矩形

共通点: frozenset[Cell] を持ち、bool_var_map のキーに使える
```

---

### Puzzle と Solution (`puzzle.py`)

**Puzzle** は変数・制約・feature を束ねる器です。**Solution** は求解結果です。

```python
p = Puzzle("name")                              # 器を作る
cell_value = p.int_var_grid("v", cells, 1, 9)   # 変数を定義 (→ feature 自動登録)
p.add(all_different(cell_value[c] for c in ...)) # 制約を追加 (→ feature 検証)
solution = p.solve()                             # 求解
value = solution.value(cell_value[cell])         # 解の値を取得
```

内部では:
1. 変数定義 → CP-SAT の `IntVar` / `BoolVar` を生成、feature を登録
2. 制約追加 → feature を検証 → 制約型に応じた CP-SAT 変換
3. 求解 → CP-SAT solver を実行 → `Solution` でラップして返す

---

## ソルバー (`packages/solvers`)

各パズルのルールを DSL で記述した具体的なソルバーです。
どのパターンを使い、どの制約を組み合わせているかを示します。

| ソルバー | パターン | 変数 | 制約 |
|---------|---------|------|------|
| **数独** | A | セル値 (1-9) | `all_different` × 行/列/ブロック |
| **スリザーリンク** | B | 辺 on/off | ヒント(`sum_expr`), 次数(`one_of`), `single_cycle` |
| **ぬりかべ** | C | セル所有者 (0..k) | サイズ(`count_eq`), 黒/島 連結(`connected`), 2×2禁止 |
| **ヤジリン** | E (A+B) | is_black + edge_on | 矢印(`sum_expr`), 黒非隣接, `single_cycle`(双対グリッド) |
| **タイリング** | D | 配置 use | `exactly_one`, 使用回数, 形状制約, 畳制約 |
| **四角に切れ** | D | 矩形 use | `exactly_one`(セル+ヒント) |

---

## 境界辺の記号

タイリングパズルの境界辺に付ける形状制約:

| 記号 | 意味 | DSL |
|------|------|-----|
| `=` | 同じ形 | `same_shape_across()` |
| `!` | 異なる形 | `different_shape_across()` |
