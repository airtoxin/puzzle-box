# 時間予算付きの小規模生成ベンチマーク

[`benchmark_generation.py`](../examples/benchmark_generation.py) は、既存の生成 CLI を
固定レシピ・指定 seed で順番に実行します。生成と保存問題の検証を別々のプロセスで測り、
各処理と全体の経過時間に予算を設けます。通常の `generate()` / `reduce_clues()` や
`generate_*.py` に時間制限を追加するものではありません。

## 実行

リポジトリのルートで、依存関係を固定して実行します。
出力ディレクトリは新しい名前にしてください。既存のディレクトリ・ファイルは上書きしません。

```sh
uv sync --all-packages --group dev --locked
uv run --no-sync python examples/benchmark_generation.py --cases shading-3x3 slitherlink-2x2 yajilin-2x3 --seeds 0 1 --phase-seconds 15 --total-seconds 90 --output benchmark-small
```

全ケースを試すには `--cases` を省略します。既定値は seed `0 1`、1処理15秒、全体120秒です。
全ケースには意図的な失敗例を含むため、正常に測定が完了しても終了コードは1になります。

```sh
uv run --no-sync python examples/benchmark_generation.py --seeds 0 1 --phase-seconds 15 --total-seconds 180 --output benchmark-all
```

予算は有限の正数で、1処理は最大300秒、全体は最大3600秒です。seed は
`0..2147483647` の異なる整数を1〜8個指定します。ケース名の重複は受け付けません。
実行順は指定したケース順、その中で seed 順です。全体予算を使い切ると残りは未実行と記録します。

## 固定ケース

| ケース名 | サイズ・設定 |
| --- | --- |
| `shading-3x3`, `shading-4x4`, `shading-5x5` | 黒数3/5/8、辺での黒非接触、白連結（非空）、白2×2禁止。セル・行数・列数ヒント、solver選択 |
| `shading-finite-3x3` | `shading-3x3` と同じ規則・ヒント、識別可能な完成盤面の有限集合から選択 |
| `slitherlink-2x2`, `slitherlink-2x3`, `slitherlink-3x3` | 非空の単一ループ、長さ指定なし。セル周囲の辺数と辺状態ヒント |
| `yajilin-2x3`, `yajilin-3x3`, `yajilin-3x4` | 黒白と単一ループの相互制約。矢印位置は0始まり `(1, 0, right)`、矢印数・辺状態ヒント、各seedで1試行 |
| `shading-insufficient-hints` | 2×2、黒数1、行数ヒントのみ。黒セルの列を区別できない |
| `shading-inconsistent` | 2×2、黒数4、黒非接触。規則が矛盾する |

サイズは各デモの上限以内です。黒白は100セル、Slitherlinkは9セル、ヤジリンは12セル、
黒白の有限選択は9セルまでで、それより大きい実用盤面の性能は調べません。
任意レシピを受け取る汎用ベンチマークや自動リトライではありません。

## 結果の読み方

出力先の `report.json` には、測定環境、Git commit、追跡ファイルの変更有無、
ベンチマークソースのSHA-256、予算、実行引数、各処理の経過秒数・終了状態を記録します。
`generate_arguments` はPythonに渡す引数で、生成先の `--output FILE --quiet` を除いたものです。
`verify_arguments` の問題ファイル名は出力ディレクトリからの相対名です。
終了したプロセスの標準出力・標準エラーは、それぞれ末尾4096文字まで記録します。

| 試行の `status` | 意味 |
| --- | --- |
| `verified` | 生成成功後、別プロセスで唯一解・保存解との一致・ヒントの既約性を検証できた |
| `generation_failed` / `verification_failed` | 対応するCLIが失敗。終了コード・エラー文を確認する |
| `generation_timeout` / `verification_timeout` | 対応するプロセスを時間予算で打ち切った。解なし・複数解とは判定していない |
| `budget_exhausted` | 全体予算が残っておらず、生成または検証を開始していない |
| `artifact_failed` | 検証応答が不正、ヒント数が不一致、ファイルを読み書きできないなどの保存処理の失敗 |

`counts` は状態ごとの件数です。成功率は「検証まで終えた件数 / 選択した試行数」とし、
時間切れや未実行を分母から外さないでください。意図的な失敗ケースは通常ケースと分けて集計します。
成功した試行の時間だけを比べると、予算で落ちた遅い試行を隠すことになります。
処理ごとの `reason` は `phase_budget` / `total_budget` など、打ち切った理由を示します。

`complete: true` は全試行の**結果を記録した**という意味で、全問成功を意味しません。
レポートは各試行後に更新します。外部から中断すると `complete: false` の最後の記録が残る場合が
あります。その場合、まだ記録されていない試行を成功率の集計から黙って外さないでください。
終了コードは、全試行検証成功が0、失敗・時間切れ・未実行がある場合は1、不正入力などが2です。

検証済みの問題はケース名とseedを含むJSONとして保存され、レポートにSHA-256が記録されます。
生成成功でも検証が失敗・時間切れなら問題を公開用ファイルへコピーしません。
一時ファイルは処理後に削除します。保存JSONは答えを含むため、問題だけ見るには例えば
次のコマンドを使います（この `show` 自体は時間予算の対象外です）。

```sh
uv run --no-sync python examples/generate_shading.py show benchmark-small/shading-3x3-seed-0.json
uv run --no-sync python examples/generate_slitherlink.py show benchmark-small/slitherlink-2x2-seed-0.json
uv run --no-sync python examples/generate_yajilin.py show benchmark-small/yajilin-2x3-seed-0.json
```

## 測定と保証の範囲

- 経過時間は単調増加時計で測り、Python起動・import・モデル構築・探索・JSON入出力を含みます。
  純粋なソルバー時間やCPU時間ではありません。ライブラリ読込のキャッシュやOS負荷も影響します。
- 生成と検証は順番に実行します。初期のseed付き探索は1 worker、ヒント削減・検証は既存ソルバーの
  worker既定値を使うため、全計算を単一CPUに固定した測定ではありません。
- 全体予算は測定開始後の経過時間です。各子プロセスの上限は「処理予算」と「全体の残り時間」の
  小さい方になります。環境情報取得は測定前です。OSのプロセス起動・終了待ち、ファイル処理などで
  実際の終了は予算を超え得ます。厳密な実時間・CPU・メモリの隔離ではありません。
- `subprocess.run(timeout=...)` で既存のPython CLIを終了・回収します。対象CLIは別プロセスを
  起動しません。任意コマンドや子孫プロセスの管理へ拡張した仕組みではありません。
- 検証器は生成器と同じDSL/CP-SATを利用します。独立した別ソルバーによる証明ではありません。
  射影は黒白セル、ループ辺、または黒白セルと辺の両方で、補助変数の別代入を別解に数えません。
- 固定seedでも、Python・OR-Tools・OS・モデルやプログラムの変更を跨ぐ一致は保証しません。
  時間やタイムアウト結果が同一になる保証もありません。比較時はcommit・環境・順序・予算を揃え、
  別の新規ディレクトリで繰り返し、成功問題のハッシュも照合してください。
- 少数の固定seedとレシピの結果から、任意の組合せの成功確率、速度、人間の難易度は推定しません。
  時点ごとの測定表・機器情報・検証結果はPRまたはissueへ記録してください。
