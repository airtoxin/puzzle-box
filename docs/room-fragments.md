# 固定した部屋を共有する黒白ルール

`ShadingRecipe` の黒白セルに、部屋ごとの個数・部屋内の連結・回転対称・行列の個数・白い直線の部屋またぎを組み合わせます。
部屋配置は**入力する固定データ**です。部屋そのものの生成・変更・削減は行いません。
解の射影は従来どおり黒白セルだけで、部屋ラベルは解の変数に含めません。

| Python / 保存・Web ID | 意味 | 条件と境界 |
| --- | --- | --- |
| `RoomBlackCount(rooms, count=2)` / `room-black-count` | 各部屋に同じ指定数の黒を置く | 0を許す。部屋ごとに異なる数は未対応。黒の形や接触を制限しない |
| `RoomConnectedBlack(rooms, nonempty=True)` / `room-connected-black` | 各部屋の黒が、その部屋の中だけを通って上下左右でつながる | 既定で各部屋に黒1個以上。`False` なら空の部屋も許す。部屋をまたぐ黒同士の接触は許す |
| `LineBlackCount(count=1)` / `line-black-count` | 各行・各列に同じ指定数の黒を置く | 0なら全白。正の数では長方形の縦横が異なると矛盾。ヒントの有無によらず残る基礎ルール |
| `NoWhiteAcrossThreeRooms(rooms)` / `no-white-across-three-rooms` | 白い直線の途中で部屋の境界を2回越えることを禁止 | 同じ部屋への再入も数える。曲がる白い経路や、1回だけの境界越えは許す |
| `RoomRotationalSymmetry(rooms)` / `room-rotational-symmetry` | 各部屋の黒配置が、その部屋の外接長方形の中心について180度対称 | 黒0個も許す。部屋外へ写るマスは白。部屋全体や白配置の対称性は要求しない |

個数は非負整数で、真偽値を数値扱いしません。盤面全体のセル数を超える値は入力エラーです。
盤面全体の範囲内でも、個々の部屋や行列に入りきらない値は矛盾になります。
`RoomConnectedBlack` は部屋外を通る迂回路を認めません。
盤面全体の黒連結が必要なら、別に `ConnectedBlack()` を組み合わせます。

## 既存パズルからの組合せ

[ニコリの「のりのり」](https://www.nikoli.co.jp/ja/puzzles/norinori/)では、各部屋に黒2個を置き、
黒の連結成分がそれぞれ2マスになります。`RoomBlackCount(rooms, 2)` と `BlackDominoes()` でこの条件を表せます。
**2マスの組は部屋の境界をまたげます**。部屋内の黒連結を追加するのは別の規則です。

[LITS](https://www.nikoli.co.jp/ja/puzzles/lits/)の部屋内の4マス連結は、
`RoomBlackCount(rooms, 4)` と `RoomConnectedBlack(rooms)` で表せます。
`ConnectedBlack()` と `NoBlack2x2()` も再利用できますが、回転・反転を含めた同じ形同士の接触禁止は未実装です。
この組合せを完全な LITS と呼ぶことはできません。

[Star Battle の規則](https://www.gmpuzzles.com/blog/star-battle-rules-and-info/)では、行・列・部屋の星数と、
星の上下左右・斜めの非接触を組み合わせます。黒を星として、`LineBlackCount(k)`、
`RoomBlackCount(rooms, k)`、`NonTouchingBlack(diagonal=True)` を使えます。
Webの描画は星記号ではなく黒マスです。ルールの成立性と、遊び応えや人間向け難易度は別です。

## レシピを保存して生成する

リポジトリのルートで実行します。既存ファイルを上書きしない出力先を選んでください。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-norinori-recipe.json --selection finite --seed 0 --output rooms.json --quiet
uv run --no-sync python examples/generate_shading.py show rooms.json
uv run --no-sync python examples/generate_shading.py verify rooms.json
```

`show` は通常のルール・ヒント・入力テンプレートに加えて、固定部屋のラベル表を表示します。
同じ数字が同じ部屋です。通常は答えを表示せず、[既存の `check`](play-shading.md) で回答を確認できます。
保存JSONには解も入ります。

- [2×3 のりのり型](../examples/shading-norinori-recipe.json)：上下の行を別々の部屋とします。解は部屋の配置だけで決まり、追加セルヒントは残りません。部屋内連結まで追加すると矛盾します。
- [2×3 部屋内連結＋黒数](../examples/shading-room-connection-recipe.json)：2つのL形の部屋に各2個の黒を置きます。複数の完成解があるため、生成器が必要なセルヒントを残します。
- [4×4 各行・列・部屋に1個](../examples/shading-star-recipe.json)：斜めも非接触とし、部屋配置だけで決まる小例です。9セルの有限生成・Webの対象外なので、以下の通常生成を使います。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-star-recipe.json --seed 0 --output stars.json --quiet
uv run --no-sync python examples/generate_shading.py show stars.json
uv run --no-sync python examples/generate_shading.py verify stars.json
```

通常のPython生成には壁時計の時間制限がありません。盤面を大きくしても短時間で終わる保証はありません。
小盤面の有限生成・診断は9セル・8ルール出現以下、保存CLIは25セル以下です。
`--rules room-black-count` などの短縮指定は既定の2×3部屋配置を使います。独自配置には保存レシピかPython APIを使ってください。

## 部屋データと UI の合成

Pythonでは `rooms=((0, 0, 1), (0, 1, 1))` のように指定します。
JSONでは二重配列を使います。盤面と同じ縦横で、全セルに `0..セル数-1` の整数ラベルが必要です。
各部屋は上下左右で連結している必要があります。空配列・凹凸のある配列・真偽値・分断された部屋は拒否します。
ラベルの数値には同じ部屋かどうか以外の意味はなく、上から行順に初登場した順で0から振り直します。

4つの部屋ルールは `rooms/cell-regions` 表示チャンネルと `region-map` パラメータを宣言します。
[Webアプリ](web-app.md)はこれを1つの共有入力欄と盤面の太い境界線に統合します。
部屋配置は1行ずつ、ラベルを空白で区切って入力します。初期配置は2×3です。寸法を変えたら配置も入力し直してください。
例えば2×3で既定ルールを外し、部屋ごと黒2個と黒2マス成分を選び、配置を次のようにすると、上ののりのり型を生成できます。

```text
0 0 0
1 1 1
```

同時に選ぶ部屋ルールは、ラベルの振り直し後に**同じ分割**を共有する必要があります。
型が同じでも異なる部屋配置は、Web・保存レシピ・保存問題の読み書きで拒否します。
ブラウザも計画の部屋配置が送信した設定と一致することを確認し、欠落・不一致なら生成と回答を停止します。
Pythonで別々の分割の条件を同じ黒白変数に課すことはできますが、この保存・表示形式では扱いません。
部屋の入力はデータだけで、ファイルからのコード実行やimportはありません。

## 検証と限界

部屋数・部屋内連結・行列数にはDSLとは別の有限判定を用意しています。
小盤面の全黒白配置とソルバーの可視解を照合し、4×4の1個配置例は行列の置換を独立列挙して確認します。
全サイズ・全組合せを証明したことにはなりません。
[説明推論](shading-deductions.md)はこの5断片の推論手順を持たず、該当番号を `rules_without_deductions` に残します。
唯一解でも、この手順では未解決になる場合があります。
部屋ごとの異なる数字、部屋の自動生成、テトロミノ形の同定、他の盤面型への部屋の接続は未対応です。

## 白い直線の部屋またぎを制限する

[へやわけの公式ルール](https://www.nikoli.co.jp/ja/puzzles/heyawake/)は、長方形の部屋で、白い直線を3部屋以上に続けることを禁止します。
`NoWhiteAcrossThreeRooms` はこの条件を、白の全体連結・黒の非接触・個数と独立に組み合わせます。
セルの連続する長さそのものは制限しません。1部屋か2部屋に収まる白い直線は、どれだけ長くてもこの断片では許されます。
途中に黒があれば白い直線はそこで切れます。
白0マスもこの断片では許します。白の存在と全体連結は、必要なら `ConnectedWhite()` で別に指定します。

このライブラリは長方形以外の連結した部屋も受理するため、一般化の意味を**部屋境界を2回越える白い直線を禁止する**と定めます。
例えば同じ行の部屋ラベルが `0 1 0` なら、異なるラベルは2種類でも3区間です。すべて白なら禁止します。
これは非長方形の部屋に対して定めた追加仕様で、公式へやわけがこの形の部屋を認めるという主張ではありません。
長方形の部屋では再入が起きないため、元の3部屋条件と一致します。

次の保存例は、2×3を3本の縦長の部屋に分け、白の連結・黒の非接触・黒2個と組み合わせます。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-room-runs-recipe.json --selection finite --seed 0 --output room-runs.json --quiet
uv run --no-sync python examples/generate_shading.py show room-runs.json
uv run --no-sync python examples/generate_shading.py verify room-runs.json
```

[例のレシピ](../examples/shading-room-runs-recipe.json)はヒントなしでは2解です。必要なセルヒントを残して一意にします。
この2解の行・列の黒数は同じなので、個数ヒントだけでは識別できません。セルヒントを候補に含めてください。
黒1個に変えると、上下の行を両方とも分断できず矛盾します。部屋ごとの異なる数ヒントはこの例に含みません。
Webでは既定の黒2個・白連結を残し、黒の非接触とこの断片を選び、部屋配置を `0 1 2` の2行にしてください。
他の部屋ルールとの同じ配置の共有、保存・表示・解答確認は上と同じです。既定の2部屋だけの配置では、この断片は冗長です。

符号化は、同じ行・列上の隣り合う境界2本をまたぐ最短区間に黒を1個以上要求します。
節の数はセル数に対して線形で、各節の長さは区間の長さです。有限判定はこれと別に、白い直線を走査して部屋への進入回数を数えます。
小盤面の全回答を照合しますが、任意サイズ・任意ルールとの組合せや人間向け難易度の保証ではありません。

## 各部屋の黒配置を180度対称にする

[Aqre (Symmetry) の公開ルール](https://www.gmpuzzles.com/blog/2024/11/aqre-symmetry-by-serkan-yurekli-2/)には、印のある部屋の黒配置を中心の周りで180度対称にする条件があります。
この断片は、**すべての部屋**について、その部屋を囲む最小の長方形の中心を使います。特定の部屋だけを選ぶ印や、任意の中心座標は指定できません。
中心は部屋配置から計算し、セルの中心、セル間の辺の中点、4セルの角のいずれにもなれます。
画面は既存の部屋境界を使い、ルールの説明に全室への適用と中心の定義を表示します。出典の円印を持つ完全な出題形式ではありません。

部屋の上端・下端を `r_min, r_max`、左端・右端を `c_min, c_max` とすると、マス `(r,c)` の像は `(r_min+r_max-r, c_min+c_max-c)` です。
像が同じ部屋にあれば黒白を等しくし、部屋外なら元のマスを白にします。別の部屋に黒があっても、元の部屋の対称配置としては数えません。
非長方形の部屋にもこの定義を使います。部屋の輪郭や白配置まで対称になるという意味ではありません。
空の黒配置も許すので、存在・個数・連結は別に指定してください。

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-aqre-symmetry-recipe.json --selection finite --seed 0 --output symmetry.json --quiet
uv run --no-sync python examples/generate_shading.py show symmetry.json
uv run --no-sync python examples/generate_shading.py verify symmetry.json
```

[保存例](../examples/shading-aqre-symmetry-recipe.json)は、[連続長の例](run-length.md)に部屋対称を追加します。
1×6の部屋で黒2個・黒連結・最大連続長3を満たす3解が、中央の黒2マスの1解になり、追加セルヒントは不要です。
部屋の中心はセル間なので、回転しても位置の変わらないセルがありません。黒は対になり、黒1個は矛盾します。
一方、1×3の部屋なら中心のセルに黒1個を置けます。唯一解やヒント不要は、一般の入力には保証しません。

Webでは同じ1×6の部屋設定に対称のルールを加えて試せます。複数の部屋ルールは1つの入力欄を共有します。
有限検査は、黒の座標集合を回転した集合と比較し、符号化のセルの等式とは別に照合します。小盤面以外や全組合せを検証したことにはなりません。
