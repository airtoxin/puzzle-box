# 信頼するPython部品を明示登録する

[合成レシピの保存](composed-recipe-files.md)は、標準では個数・連結の2部品だけを扱います。
開発者は、自分が信頼するPython部品とパラメータの検証規則を登録した値を、読込・保存・生成・検証に
明示的に渡せます。ファイルに書かれたモジュールをimportする仕組みや、プラグインの自動探索はありません。

## 実例を試す

[自作部品の例](../examples/custom_row_band.py)は `RowBlackBand(minimum, maximum)` です。
各行の黒セル数を上下限で制限し、`example/row-black-band/v1` というIDで登録します。
[設定例](../examples/custom-row-band-recipe.json)は、白連結の2×3盤面に、標準の「黒2個」と自作の
「各行の黒は0～1個」を組み合わせます。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/custom_row_band.py generate --recipe examples/custom-row-band-recipe.json --seed 0 --output row-band-puzzle.json
uv run --no-sync python examples/custom_row_band.py verify row-band-puzzle.json
```

自作部品を登録したPythonの入口を、利用者が明示的に選んでいます。標準の
`generate_composed_shading.py` でこのファイルを読めば、未知のIDとして拒否します。
ファイルから入口を選択したり、足りないコードを取得したりはしません。出力先は新規ファイルに限り、JSONには答えも入ります。

## 部品と登録表を書く

部品は `@dataclass(frozen=True)` とし、`__call__(puzzle)` がそのモデルのDSL制約を列挙して返します。
設定は固定とし、ヒント・求解結果・呼び出し回数に依存しない[生成契約](recipe-constraint-composition.md)を守ります。
部品自体の実装は例の `RowBlackBand` を参照してください。

次は `examples` で実行するPythonコードの登録・書出し・読込例です。

```python
from generator import with_constraints
from puzzle_defs import ConnectedWhite, ShadingRecipe
from component_registry import IntParam
from composed_shading_recipe import BUILTIN_COMPONENTS, CellCount, recipe_record, read_recipe
from custom_row_band import RowBlackBand
from generate_composed_shading import generate_record, verify

components = BUILTIN_COMPONENTS.with_component(
    "example/row-black-band/v1", RowBlackBand,
    minimum=IntParam(0, 9), maximum=IntParam(0, 9),
)
recipe = with_constraints(
    ShadingRecipe(2, 3, (ConnectedWhite(),)),
    CellCount("black", 2), RowBlackBand(0, 1),
)
record = recipe_record(recipe, registry=components)
restored = read_recipe(record, registry=components)
puzzle_record = generate_record(record, seed=0, registry=components)
assert verify(puzzle_record, registry=components)["valid"]
```

`load_recipe(path, registry=components)` も使えます。CLIを用意する場合は、信頼するコードを静的にimportし、
`generate_composed_shading.main(registry=components)` を呼びます。全操作で同じ登録表を渡してください。
登録表は変更不能で、`with_component` は新しい値を返します。元の登録表や標準CLIの対応部品は変わりません。

## パラメータの契約

対応するのは平坦なプリミティブ設定です。データクラスの全コンストラクタフィールドを登録し、保存時にもすべて明示します。
追加・不足フィールドは拒否し、`id` は予約語です。`InitVar`、`init=False`のフィールド、任意の変換関数は扱いません。
`with_component(ID, 型, **検証規則)` のIDと型は位置引数で渡します。`identifier`、`builder_type`、`self` も
部品のフィールド名として使えます。検証規則のキーワード引数の順序は互換性に影響せず、データクラスの宣言順に保持します。
登録時には、全パラメータをキーワード引数として渡せることも検査します。位置専用引数など、
復元に使う呼出し方に対応しないコンストラクタは登録できません。通常の引数とキーワード専用引数は使えます。

| 検証規則 | 受理する値 |
| --- | --- |
| `IntParam(minimum, maximum)` | 両端を含む範囲の整数。真偽値・小数は不可 |
| `ChoiceParam(("black", "white"))` | 明示された有限個の文字列のいずれか |
| `BoolParam()` | 真偽値のみ。0や1は不可 |

ファイルのID・フィールド・型・範囲を検査した後、**登録済みの信頼するコンストラクタ**を呼びます。
上下限の大小など複数フィールドの関係は `__post_init__` で検査し、不正なら `ValueError` にします。
入力値の丸めや書換えは保存内容の意味を変えるため拒否します。コンストラクタは値を保持し、検査だけを行ってください。
レシピの書出し時にも読込と同じ検証のため登録済みコンストラクタを呼びます。呼び出し回数に依存せず、同じ設定を再構築できる必要があります。

同じIDの再登録と、同じ型を別IDで登録することはエラーです。後者は書出し先IDが曖昧になるためです。
書出しは登録した型との完全一致で選び、未登録のサブクラスは親へ変換しません。
黒白保存形式で使う登録表は、標準部品のID・型・検証規則をすべて保持する必要があります。

## 非信頼データと信頼済み実装の境界

JSONは登録表やPython型を定義できません。指定できるのは、登録済みIDと上の検証に通る値だけです。
未知ID・版・`module`やコードなどの余分な項目は拒否します。import先、関数名、eval、pickleをデータから解決しません。

一方、登録するPythonコードには通常のPythonと同じ権限があります。このAPIはそのコードを隔離するサンドボックスではありません。
コンストラクタと部品の副作用・実行時間・ルールの意味・単調性を自動で証明しません。第三者の登録コードは信頼できるか確認してから使い、
独立した小盤面列挙と保存前後の解集合をテストしてください。凍結データクラスでも、外部の可変状態に依存する実装は生成契約を満たしません。
合成APIは部品終了時の回答選択の変更を拒否しますが、これもPythonコード全般の安全性を保証するものではありません。

IDは小文字の名前と `/v1` などの正整数の版で終える形式です。自作部品は `acme/row-band/v1` のように組織や用途の名前を付けてください。
衝突検査は渡した登録表内で行い、別の配布物が同じIDへ同じ意味を割り当てていることまでは証明しません。
意味や設定の互換性を変える場合は新しい版と型を定義し、移行を明示します。ファイルと一緒に必要な信頼済みコードの版も管理してください。

既存の2部品のJSONと呼出し方は維持しています。新しいIDを知らない古い読込側はエラーになり、部品を無視して別の問題として扱いません。
盤面は引き続き9セル以下の黒白で、ループや任意の盤面型への拡張点ではありません。8部品・65,536バイトの制限も変わりません。
大きな探索、厳密な時間上限、表示・解答入力・説明推論への自動接続は未対応です。

## 登録と各機能の対応は別の契約

登録は部品の保存・復元を可能にします。独立な盤面判定や説明可能な推論手順を自動で追加するものではありません。

| 操作 | 登録済み部品を含む問題 |
| --- | --- |
| `generate_composed_shading.generate_record` / `verify` | 同じ信頼済み `registry` を明示して生成・唯一解・ヒント既約性を検証 |
| `analyze_shading` / `finite_shading` | 未対応。完全一致する `ShadingRecipe` と既知4ルールだけが対象 |
| `diagnose_shading_rules` | 未対応。既存の `shading-v1/v2` だけが対象 |
| 既存の表示・解答入力・説明推論・候補の推論比較 | 合成保存形式は未対応。通常の黒白形式へ変換して部品を省略しない |

有限診断と旧レシピ形式への書出しは、`ConstrainedRecipe` と `ShadingRecipe` の派生クラスを実行前に拒否します。
派生クラスが `build_from_clues` などへ条件を追加すると、`rules` 欄だけで列挙・保存した解集合は元の問題と異なるためです。
`recipe.base` だけを渡す方法も、追加部品のない別問題を調べる操作です。元の問題への保証として使えません。

旧 `shading-v1/v2` に `components` などの未知項目を足しても拡張できません。検証・表示はそれらを無視せず拒否します。
既存の任意項目 `seed` と `environment` は維持しますが、由来のメタデータであり、ルールの定義場所ではありません。
追加の参考情報は `"environment": {"label": "作成メモ", "ratio": 1.25}` のように既存の欄内へ置きます。
これらの項目を省略しても検証できます。環境欄に書かれた値を追加制約として実行することはありません。
任意のトップレベル項目を無視していた読込側とは互換性が異なり、`extra_metadata` のような項目も拒否します。
既存ファイルの追加項目が参考情報だけであると確認した場合に限り、手動で `environment` へ移してください。
未知の項目を自動移動したり削除したりはしません。追加ルールやヒントには、その意味を扱える保存形式が必要です。
未対応は「矛盾」「複数解」「推論が途中で停止した」とは異なります。形式エラーをそれらの判定に読み替えないでください。
