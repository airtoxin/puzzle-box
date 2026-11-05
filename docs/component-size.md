# 色の連結成分を同じサイズにする

`ColorComponentSize(size, black=True)` は、対象色の各連結成分を、ちょうど `size` マスにします。
上下左右でつながる成分だけを数え、斜めの接触は許します。対象色0マスも許します。
`black=False` なら白が対象です。全体の個数・成分の個数・黒白の存在は別の条件です。

Python・保存CLI・Webでは最大100セルです。対象サイズは1〜盤面積の厳密な整数で、真偽値などを数値に変換しません。大盤面は計算時間がかかり、Webの予算内に生成できる保証はありません。

## パズルの条件として使う

[のりのりの公式ルール](https://www.nikoli.co.jp/ja/puzzles/norinori/)には、黒の各成分が2マスになる条件があります。
黒・サイズ2はその条件で、既存の `BlackDominoes()` と同じ回答集合です。部屋ごとの黒2個は別に指定する必要があり、成分は部屋境界をまたげます。
黒・サイズ1は、上下左右の黒非接触と同じです。

[ぬりかべ](https://www.nikoli.co.jp/ja/puzzles/nurikabe/)では、数字が白い島の面積を指定します。
白・サイズ3などは同じ面積の島を作る条件の一般化ですが、数字の位置・各島に数字1個・数字マスは白という条件は含みません。
現在の[固定数字の断片](number-fragments.md)は重複禁止のラベルであり、島の面積ヒントに読み替える仕組みではありません。
これだけで完全なぬりかべを実装したことにはなりません。

## 生成して確かめる

```sh
uv run --no-sync python examples/generate_shading.py generate --recipe examples/shading-component-size-recipe.json --selection finite --seed 0 --output components.json --quiet
uv run --no-sync python examples/generate_shading.py show components.json
uv run --no-sync python examples/generate_shading.py verify components.json
```

- [黒3マス成分＋黒6個＋白連結](../examples/shading-component-size-recipe.json)：3×3。黒は離れた3マス成分2個です。
- [白3マス成分＋黒3個＋黒連結＋黒2×2禁止](../examples/shading-equal-islands-recipe.json)：3×3。白い島2個と黒い帯を作ります。

どちらも、中央の白／黒の帯が横か縦かの2解です。生成器が必要なセルヒントを残して一意にします。
上の `--recipe` を入れ替えて同じ手順を使えます。通常の `show` は解を隠しますが、保存JSONには完全な解が含まれます。

Webでは3×3で、既定の白連結を残し、黒数6とサイズ3・黒対象を選ぶと最初の組合せを試せます。
白対象・黒数3に変えて白連結を残すと、白6マスを1成分にする要求とサイズ3が矛盾します。
白連結を外し、黒連結を選ぶと白い島の例になります。`NoBlack2x2()` も追加できますが、この小例では冗長です。
同じルールを両色で同時に使う場合、Pythonと保存レシピでは複数出現を使えます。Webは同一IDを1回だけ選ぶ既存方針のままです。

## 実装・一意性・計算量

各対象セルに成分ラベルを付け、隣接する対象色のセルは同じラベルにします。各成分の代表セルへ向かう深さが減る親辺を設けることで、離れた成分が同じラベルを共有できないようにします。代表ごとのセル数を指定サイズにします。補助変数は回答に含めず、唯一性は黒白セルだけで判定します。Webの時間予算内に証明できないときは未確定です。

有限検査は配置変数を使わず、座標集合の連結成分を数えます。小盤面の全回答と、列挙処理を別の組合せ列挙・到達可能性検査と照合します。
任意サイズや全ルール組合せの検証ではありません。[説明推論](shading-deductions.md)にはこの断片の手順がなく、未対応ルール番号を報告します。
保存IDは `color-component-size`、パラメータは `size` と `black` だけです。未知ID・余計なフィールド・サブクラスを拒否し、任意コードを読み込みません。
