# Puzzle Box Architecture

## 概要

puzzle-box は **パズル DSL** (`packages/puzzle`) と **ソルバー集** (`packages/solvers`) から構成される Python モノレポです。DSL は CP-SAT (Google OR-Tools) をバックエンドとし、パズルのルールを宣言的に記述できます。

```
Puzzle DSL (puzzle)          Solvers (solvers)
┌─────────────────────┐      ┌──────────────────┐
│ Grid Topology       │      │ sudoku            │
│ Variables & Exprs   │◄─────│ slitherlink       │
│ Constraints         │      │ nurikabe          │
│ Enumeration/Filter  │      │ yajilin           │
│ Features/Validation │      │ tiling            │
│ Puzzle & Solution   │      │ shikaku           │
└─────────────────────┘      └──────────────────┘
         │
         ▼
    CP-SAT (ortools)
```

---

## 概念レイヤー

### 1. グリッドトポロジー (`grid.py`)

空間構造の基盤。すべてのパズルはこのレイヤーの上に構築されます。

#### 型

| 型 | 説明 |
|---|---|
| `Cell(row, col)` | マス目。パズルの基本単位 |
| `Vertex(row, col)` | 格子点。辺の端点 |
| `Edge(v1, v2)` | 辺。2つの隣接する格子点を結ぶ。正規化済み (`v1 < v2`) |
| `SquareGrid` | 矩形グリッド。上記3要素の関係を管理 |

#### 関係

```
Cell ←──edges_around──── Edge ────edges_incident──→ Vertex
 │                        │                          │
 │  cells_sharing_edge    │    _make_edge             │
 │◄───────────────────────│◄──────────────────────────│
 │                        │
 │  neighbors             │  (2つの Cell を分離)
 │──────→ Cell            │
```

#### SquareGrid のビュー

| メソッド | 戻り値 | 用途 |
|---------|--------|------|
| `cells` | 全セル | 変数の定義域 |
| `rows()` / `cols()` | 行/列ごとのセル | 数独の行列制約 |
| `blocks(h, w)` | 非重複ブロック | 数独の 3×3 ボックス |
| `windows(h, w)` | 重複部分矩形 | ぬりかべの 2×2 プール禁止 |
| `neighbors(cell)` | 隣接セル | 連結性、隣接制約 |
| `vertices` / `edges` | 全頂点/辺 | スリザーリンクのループ |
| `edges_around(cell)` | セルを囲む4辺 | スリザーリンクのヒント |
| `edges_incident(vertex)` | 頂点に接する辺 | 頂点次数制約 |
| `cells_sharing_edge(edge)` | 辺の両側のセル | 境界形状制約 |

---

### 2. 変数と式 (`expr.py`)

CP-SAT の変数を公開 API でラップし、ortools への依存を隠蔽します。

#### 型階層

```
Expr                  ← CP-SAT LinearExpr のラッパー
├── Var               ← 単一の整数決定変数 (IntVar)
│   └── __eq__/__ne__ → BoolExpr を返す (reification)
└── BoolExpr          ← 0/1 indicator。制約としても式としても使える
         │
         ▼
    LinearConstraint  ← BoundedLinearExpression のラッパー
```

#### Var の比較演算子と reification

`Var` の `==` / `!=` は **`BoolExpr`** を返します。これが DSL の中核的な仕組みです。

```python
owner[c] == 0    # → BoolExpr (indicator 変数)
```

`BoolExpr` は内部で完全 reification を行います:
```
indicator == 1  ↔  元の制約が成立
```

これにより、同じ式を3つの文脈で使えます:

| 文脈 | 例 | 動作 |
|------|---|------|
| 制約として | `p.add(owner[c] == 5)` | indicator を 1 に固定 |
| 式として | `sum_expr(owner[c] == 0 for c in ...)` | indicator の合計 = カウント |
| 述語として | `connected(predicate=lambda c: owner[c] == 0)` | indicator で活性セル判定 |

#### 変数コンテナ

| 型 | キー | 生成メソッド |
|----|------|------------|
| `VarGrid` | `Cell` | `p.int_var_grid()` |
| `VarMap` | 任意の `Hashable` | `p.int_var_map()`, `p.bool_var_map()` |

---

### 3. 制約 (`constraints.py`, `polyomino.py`)

パズルのルールを表現するオブジェクト。`Puzzle.add()` で追加します。

#### 制約の分類

```
制約
├── 値制約 ─────── 変数の値に関する制約
│   ├── LinearConstraint    (==, !=, <=, >= 等)
│   ├── BoolExpr            (reified 等式)
│   ├── AllDifferentConstraint
│   ├── OneOfConstraint
│   ├── UniqueConstraint    (唯一解)
│   └── sum_expr / count_eq / exactly_one (集約)
│
├── 位相制約 ───── グラフ構造に関する制約
│   ├── SingleCycleConstraint  (単一閉路)
│   └── ConnectedConstraint    (連結性)
│
└── 領域制約 ───── 領域分割に関する制約
    ├── ShapeAcrossConstraint       (境界辺の形状条件)
    │   ├── same_shape_across       (= 同形)
    │   ├── different_shape_across  (! 異形)
    │   └── all_adjacent_different_shape (全隣接異形)
    └── NoBoundaryCrossConstraint   (十字交差禁止)
```

#### 各制約の詳細

| 制約 | require | CP-SAT 実装 |
|------|---------|------------|
| `all_different(vars)` | `cell_vars` | `add_all_different` |
| `one_of(*constraints)` | — | `add_exactly_one` + `only_enforce_if` |
| `unique()` | — | 全解列挙 (2つ目で打ち切り) |
| `sum_expr(exprs)` | — | `LinearExpr.sum` |
| `count_eq(exprs, n)` | — | `sum_expr == n` |
| `exactly_one(exprs)` | — | `sum_expr == 1` |
| `single_cycle(edges, grid)` | `edge_vars` | `add_circuit` + 双方向アーク + セルフループ |
| `connected(cells, pred)` | `cell_vars` | スパニングツリー (親ポインタ + 順序変数) |
| `same_shape_across(edge, ...)` | `region_partition`, `shape_class` | ペアワイズ排除 (`use[pa] + use[pb] <= 1`) |
| `different_shape_across(edge, ...)` | `region_partition`, `shape_class` | 同上 (条件逆転) |
| `all_adjacent_different_shape(...)` | `region_partition`, `shape_class` | 全隣接ペアに適用 |
| `no_boundary_cross(...)` | `region_partition` | 各内部頂点で bridge >= 1 |

---

### 4. Feature と検証 (`features.py`)

制約の前提条件を宣言的に管理します。

```
Puzzle
├── _features: set[str]     ← 登録済み feature
├── add_feature(name)       ← 手動登録
├── int_var_grid()          ← 自動で "cell_vars" 登録
├── int_var_map()           ← 自動で "cell_vars" 登録
├── bool_var_map()          ← 自動で "edge_vars" 登録
└── add(constraint)
    └── _check_requires()   ← 不足時に MissingFeatureError
```

| Feature | 意味 | 登録タイミング |
|---------|------|-------------|
| `cell_vars` | セル変数が定義済み | `int_var_grid()`, `int_var_map()` |
| `edge_vars` | 辺変数が定義済み | `bool_var_map()` |
| `region_partition` | セルが領域に分割される | `add_feature()` (手動) |
| `shape_class` | 各領域に形状名がある | `add_feature()` (手動) |

不足時のエラー例:
```
ShapeAcrossConstraint cannot be used here.

Missing features:
  - region_partition: cells are partitioned into non-overlapping regions
  - shape_class: each region has a named shape type

Hint:
  Define a region partition via placement-based exact cover.
  Use polyomino placements with named piece types.
```

---

### 5. 列挙とフィルタリング (`polyomino.py`, `shikaku.py`, `regions.py`)

ソルバーの前処理。CP-SAT に渡す前の組合せ列挙です。

#### ポリオミノ系 (`polyomino.py`)

```
polyomino(name, cells, rotate, reflect)
    → Polyomino (名前 + バリエーション集合)
        → enumerate_placements(board, piece, walls)
            → list[Placement] (piece_name + cells)
```

| 関数 | 入力 | 出力 |
|------|------|------|
| `polyomino()` | 形状定義 + 変換オプション | `Polyomino` (最大8バリエーション) |
| `enumerate_placements()` | 盤面 + ピース + 壁 | 有効配置リスト |

#### 四角に切れ系 (`shikaku.py`)

```
enumerate_shikaku_rectangles(board, clues)
    → list[ShikakuRect] (clue_cell + cells)
```

ヒントセルを含み面積が一致する全矩形を列挙。

#### 汎用領域系 (`regions.py`)

```
enumerate_connected_regions(board, size)  → list[Region]  (自由形状)
enumerate_rectangles(board, size)         → list[Region]  (矩形のみ)
    │
    ▼ フィルタパイプライン
filter_one_number_per_region(regions, numbers)       → 数字1つの領域
filter_number_equals_area(regions, numbers)           → 数字=面積の領域
filter_same_number_combination(regions, numbers, n)   → 同じ数字組合せの領域
```

#### 領域型の関係

```
Region(cells, clue_cell?)      ← 汎用領域
Placement(piece_name, cells)   ← ピース配置 (= 名前付き領域)
ShikakuRect(clue_cell, cells)  ← 四角に切れ矩形
```

すべて `frozenset[Cell]` を持ち、`bool_var_map` のキーとして使えます。

---

### 6. Puzzle と Solution (`puzzle.py`)

パズル定義と求解のオーケストレーター。

```python
p = Puzzle("name")                              # 1. パズル作成
cell_value = p.int_var_grid("v", cells, 1, 9)   # 2. 変数定義
p.add(all_different(cell_value[c] for c in ...)) # 3. 制約追加
solution = p.solve()                             # 4. 求解
value = solution.value(cell_value[cell])         # 5. 解の取得
```

#### ライフサイクル

```
Puzzle.__init__
    │
    ├── int_var_grid() / int_var_map() / bool_var_map()
    │       ↓ feature 自動登録
    │       ↓ CP-SAT 変数生成
    │
    ├── add_feature()  ← 手動 feature 登録
    │
    ├── add(constraint)
    │       ↓ _check_requires()  ← feature 検証
    │       ↓ 制約型に応じた CP-SAT 変換
    │
    └── solve()
            ↓ CP-SAT solver 実行
            ↓ unique() 設定時は全解列挙
            → Solution | None
```

---

### 7. ソルバー (`packages/solvers`)

各パズルのルールを DSL で記述した具体実装。

| ソルバー | 変数 | 主な制約 | 特殊技法 |
|---------|------|---------|---------|
| **数独** | `int_var_grid` (1-9) | `all_different` × 行列ブロック | — |
| **スリザーリンク** | `bool_var_map` (辺) | `sum_expr` + ヒント, `one_of`(次数), `single_cycle` | — |
| **ぬりかべ** | `int_var_map` (所有者) | `count_eq`, `connected` × (黒+各島), `sum_expr`(2×2禁止) | `BoolExpr` で所有者を indicator 化 |
| **ヤジリン** | `bool_var_map` (is_black + edge_on) | `sum_expr`(矢印), 黒非隣接, `single_cycle` | 双対グリッド (`square_grid(h-1, w-1)`) |
| **タイリング** | `bool_var_map` (配置) | `exactly_one`(exact cover), `max_uses` | `region_partition` + `shape_class` feature |
| **四角に切れ** | `bool_var_map` (矩形) | `exactly_one`(セル+ヒント) | `ShikakuRect` でヒント付き矩形列挙 |

---

## パズル → 制約のマッピングパターン

### パターン A: セル値 + 全異制約 (数独型)

```
int_var_grid → all_different
```

### パターン B: 辺ブール + ループ (スリザーリンク型)

```
bool_var_map(edges) → sum_expr(ヒント) + one_of(次数) + single_cycle
```

### パターン C: セル所有者 + 連結性 (ぬりかべ型)

```
int_var_map(owner) → count_eq + connected + BoolExpr
```

### パターン D: 配置選択 + Exact Cover (タイリング型)

```
enumerate_placements/regions → bool_var_map(placements) → exactly_one per cell
                               + shape_across / no_boundary_cross
```

### パターン E: 双対グリッド (ヤジリン型)

```
square_grid(h-1, w-1)  ← セル = 頂点, 隣接 = 辺
bool_var_map(dual.edges) + single_cycle(dual)
sum_expr(edges + [is_black, is_black]) == 2  ← 黒/ループのリンク
```

---

## 境界辺の記号

タイリングパズルの境界辺に付ける形状制約の記号:

| 記号 | 意味 | DSL |
|------|------|-----|
| `=` | 同じ形 | `same_shape_across()` |
| `!` | 異なる形 | `different_shape_across()` |
