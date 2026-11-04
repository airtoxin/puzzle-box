# 保存問題の読込と互換性

保存JSONには問題のヒントと答えが含まれます。答えを見ずに遊ぶには、ファイルを直接開かず
対応するCLIの `show` を使います。`verify` は唯一解・保存された答えとの一致・ヒントの既約性を確認し、
`check` はその検証後に入力した完成回答を照合します。

## 対応する形式

| `format` | 読込先 | 内容 |
| --- | --- | --- |
| `puzzle-box/shading-v1` | `generate_shading.py` | セルヒントの黒白問題 |
| `puzzle-box/shading-v2` | `generate_shading.py` | セル・行・列のヒントを使う黒白問題 |
| `puzzle-box/slitherlink-v1` | `generate_slitherlink.py` | セル外周の辺を回答にする問題 |
| `puzzle-box/yajilin-v1` | `generate_yajilin.py` | 黒セルとセル中心間の辺を回答にする問題 |

```sh
uv run --no-sync python examples/generate_shading.py show examples/shading-mixed-sample.json
uv run --no-sync python examples/generate_slitherlink.py verify examples/slitherlink-sample.json
uv run --no-sync python examples/generate_yajilin.py show examples/yajilin-sample.json
```

トップレベルはオブジェクトで、対応する `format` が必要です。未知の版や別のパズル型は拒否します。
自動の版移行や古い形式への読み替えはありません。未知の版を開けないときは対応する読込処理を用意してください。
`format` の文字列だけを書き換えても、ルール・回答・ヒントの意味を安全に変換できません。

探索レポート、[設定だけのレシピ](shading-recipe-files.md)、実験用の
[coupled保存問題](coupled-clue-contribution.md)は別形式です。表のCLIで相互に読み替えることはできません。

## ファイル読込の条件

上記の `show` / `verify` / `check`、レシピの読込、保存問題の診断は、共通のJSON読込処理を使います。

- UTF-8、BOMなし、最大65,536バイトです。空白も上限に含み、文字数ではなくバイト数で数えます。
- 同じオブジェクト内のキーの重複は、入れ子の中でも拒否します。後に書いた値で上書きしません。
- `NaN`、`Infinity`、`-Infinity` と、`1e400` のように浮動小数点の無限大になる数値は拒否します。
- JSONとして壊れた入力、文字コード不正、読込処理で扱えない深さの入れ子はエラーになります。
  入れ子の許容深さはPythonの実行環境に依存し、固定の互換性保証ではありません。

例えば次のような曖昧な入力は、既知の版として読み込まず、`Duplicate JSON key: format` で失敗します。

```json
{"format": "puzzle-box/shading-v99", "format": "puzzle-box/shading-v1"}
```

読込エラーはCLIの標準エラーに理由を表示し、終了コード2になります。入力ファイルは変更しません。
正規のv1・v2のデータは引き続き読み込めますが、重複キー、非有限数、上限超過を含むファイルは対象外です。
大きすぎるファイルは、まず不要な空白やメタデータを確認してください。ルールやヒントを削除すると問題の意味が変わります。

## メタデータと検証の範囲

各形式が使用する配列項目（`rules`、`clue_kinds`、`clues`、`arrow_sites`、回答のセル・辺一覧など）は
JSONの配列 `[...]` で指定します。空の一覧は `[]` です。`{}`、文字列、`null`、真偽値は代用できず、
例えば `solution.black_cells must be an array` のように項目名付きでエラーになります。
`clue_kinds` に `{"cell": false}` を渡してキーだけをヒント種別として読むこともありません。
黒白v1のセルヒントは `[行, 列, 値]` の3要素です。正しい配列でも要素・座標・盤面の条件は別途検証します。
Pythonから保存記録の読込関数を呼ぶ場合も配列は `list` にします。レシピ自体のPython APIで使うタプルは変更しません。

通常の保存問題では `seed` と `environment` は必須ではなく、解の正しさは盤面・ルール・ヒントから検証します。
Yajilinの `generation` がある場合は、成功seedと試行回数の整合性も確認します。
追加の参考情報は既存の `environment` 内へ置きます。例えば `"environment": {"label": "作成メモ", "ratio": 1.25}`
は解の意味を変えないメタデータです。項目を省略したファイルと、こうした参考情報を含むファイルの両方を扱えます。
`environment` 内の値を制約として解釈・実行することはありません。

未知のトップレベル項目の受理は、形式間で共通の互換性保証ではありません。読込側が無視する場合も、
追加項目として拒否する場合もあります。レシピ設定とcoupled診断用の形式も追加項目を拒否します。
`extra_metadata` などを使ったファイルは、その内容が参考情報だけであると確認してから手動で `environment` へ移してください。
未知の項目を自動移動すると追加ルールを隠す恐れがあるため、自動移行は行いません。
新しい意味を持つルールやヒントには対応する保存形式を使い、メタデータとして保存してはいけません。

共通読込はファイルとJSONの境界を検証するもので、完全なJSON Schema検証ではありません。
盤面やヒントの制約は各形式の読込処理が担当します。Pythonから直接 `verify(dict)` などを呼ぶ場合、
すでに失われた重複キーや元ファイルのバイト数は検査できません。ファイルの検証にはCLIか共通読込を使ってください。

65,536バイトの制限はソルバーの計算時間上限ではありません。各例の盤面サイズ制限も引き続き適用されます。
一意性やヒントの既約性は、人間の解きやすさや最少ヒント数を意味しません。
