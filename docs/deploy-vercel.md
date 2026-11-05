# Vercelで小盤面のWebデモを動かす

ローカル用の `examples/web_server.py` は外部公開しません。Vercelでは静的画面と1つのPython関数を使い、
既存のカタログ・入力検証・生成・解答確認を再利用します。対応する盤面やルールは[Webアプリの説明](web-app.md)と同じです。

## 配信物を作る

Python 3.12を使います。リポジトリのルートで、まだ存在しない出力ディレクトリを指定します。

```sh
python examples/prepare_vercel.py build/vercel-artifact
```

出力済みディレクトリは上書きしません。更新時は別の出力先を指定してください。
エクスポートにはGitが必要で、新しい実行モジュールは先に追跡対象に含める必要があります。
追跡中の作業ツリーの内容を読むため、デプロイ元のコミットと未コミット変更の有無を確認してください。

- `public/`: 画面のHTML・CSS・JavaScriptだけ。
- `api/index.py`: 信頼済みのローカルソースと依存パッケージを読み込むWSGI入口。
- `examples/` と `packages/`: 明示したWeb用モジュールと既存ライブラリのPythonソース。テストは含みません。
- `requirements.txt`: このWeb構成が使う実行時依存のバージョンを `uv.lock` から固定。開発用ツールは含みません。
- `.python-version` と `vercel.json`: Python 3.12、静的出力、APIの転送、関数の上限とヘッダー。

`.git`、`.venv`、`.env`、ローカルの作業記録を丸ごと送ることはありません。
実行時依存を増やす場合は、エクスポーターの依存集合とパッケージ集合も更新し、独立した配信物で生成を検証してください。
バージョンだけを固定しても、異なるOSやプラットフォーム更新をまたぐ同一出力は保証しません。

## デプロイ先と実行方式

### Git連携からビルドする

リポジトリのルートにも `vercel.json` と `api/index.py` があります。Git連携ではルートを対象に、
既存プロジェクトの Settings → Git からリポジトリを接続し、Production Branch を `main` に指定します。
Root Directory はリポジトリのルート、Framework Preset は Other を使い、ビルド・出力・関数設定は
ルートの `vercel.json` に従います。[正式な接続手順](https://vercel.com/docs/git/vercel-for-github)は
Vercel側の所有権と既存GitHub Appのアクセス権が必要です。設定ファイルを追加するだけでは接続や自動デプロイは有効になりません。

Gitビルドはレビュー対象のリポジトリをVercelへ渡します。実行時依存はルートの `pyproject.toml` と `uv.lock` から解決し、
開発環境のコピーを使いません。`api/index.py` は配信物方式と同じWSGI入口を再利用します。
ルートの `package.json` は静的ビルドの検出用で、追加のnpm実行時依存はありません。
静的ビルドは `python3 examples/prepare_web_static.py` でHTML・CSS・JavaScriptの3ファイルだけを
`build/vercel-public` へコピーするため、`apps/web/tests` や `node_modules` を公開しません。
関数からも静的画面・文書・テスト・開発環境を除外します。Gitビルドのソース集合は、次の専用エクスポート方式と異なります。

既存プロジェクトを再利用し、接続のために同名の新規プロジェクトを作らないでください。
認証済みCLIを使う場合は、対象を確認して `vercel git connect` を実行する方法もあります。
新しいログイン・トークン・GitHub Appのアクセス権が必要なときは、接続操作と権限付与を区別してください。
CIからの独自デプロイとGit連携の二重設定は避けます。接続後は、まずプレビューのビルド・カタログ・小盤面生成を検証し、
本番への反映と配信元コミットを確認してください。Git連携だけでGitHubのCIやレビューが本番配信の前提になるわけではありません。

### 専用配信物を送る

Git連携を使わない場合は、既存のVercelプロジェクトを確認し、上で作った配信物のディレクトリを対象にデプロイします。
APIからファイルを送る方法でも、認証済みのVercel CLIで配信物をリンクして送る方法でも利用できます。
CLIでは、対象チームと既存プロジェクトを明示します。

```sh
vercel link --cwd build/vercel-artifact --project PROJECT_NAME --scope TEAM_SLUG
vercel deploy --cwd build/vercel-artifact --prod --scope TEAM_SLUG
```

この手順にGitHub連携の追加は必要ありません。接続・権限・保護設定を変える操作はデプロイとは分けて判断してください。
認証トークンをソース、シェル引数、PR、ログに貼り付けないでください。
本番エイリアスの割当と保護の適用先はVercel側の設定に従います。保護されたURLはログインが必要です。

Vercelの[Python関数](https://vercel.com/docs/functions/runtimes/python/api-directory)はWSGIを受け取れます。
`/api/catalog`、`/api/plan`、`/api/generate`、`/api/check` を同じ関数へ転送し、コードで操作を検査します。
実行環境は依存パッケージの探索パスを追加するため、子プロセスにも親の `sys.path` を引き継ぎます。
開発者のeditable installや、Python実行ファイルだけから依存を見つけられるという前提には依存しません。

## 計算とアクセスの制限

| 対象 | このデモの制限 |
| --- | --- |
| 盤面 | 黒白最大100セル（ルール固有の9・10セル上限あり）、スリザーリンク4セル、複合9セル。未知のルールやアップロードコードは拒否 |
| 生成・解答確認 | 1回1〜10秒。子プロセスの起動・import・計算を含む。超過時は終了・回収して `timeout` |
| 関数全体 | `maxDuration: 30`。起動・終了・応答の余裕を含む。プラットフォームの終了ではJSONが返らないことがある |
| 同時実行 | **Pythonインスタンス内**で生成・確認を合わせて1件。混雑時は409。全インスタンス共通の制限ではない |
| JSON本文 | 32,768バイト以下、重複キー・非有限数・未知形式・余分なフィールドを拒否 |
| Origin / Host | Vercelが設定するデプロイ・本番・ブランチのホストを許可し、POSTは同じHTTPS Originのみ |
| 永続化 | 保存はブラウザのダウンロード。サーバーへの任意パス書込みや永続ジョブはない |

Origin検査はユーザー認証ではありません。APIクライアントはヘッダーを送れるため、公開URLには匿名の計算要求が届きます。
分散した利用者別レート制限・全体のCPU予算・待ち行列は実装していません。Vercelの複数インスタンスをまたぐロックとも扱いません。
広い公開や継続的な高負荷利用には、アクセス方針と分散制限を別途設計してください。
既存の保護を自動で解除したり、共有用の認証リンクを作ったりはしません。

[Pythonランタイムの説明](https://vercel.com/docs/functions/runtimes/python)と
[関数の制限](https://vercel.com/docs/functions/limitations)では、標準のPython関数は非圧縮500MBまでです。
OR-Toolsにはネイティブバイナリが含まれるため、Windowsの環境をコピーせず、VercelのLinuxビルドで固定依存をインストールします。
ソースのサイズと依存込みの関数サイズは異なります。ビルド成功を確認してから実URLで生成してください。

[Hobbyプラン](https://vercel.com/docs/plans/hobby)は無料枠で、利用枠を超えると機能が停止する場合があります。
デプロイが成功しても継続的な可用性や残りの枠は保証しません。この構成から有料プランやアドオンを有効にすることはありません。
具体的な利用量・料金・上限は、現在の契約とダッシュボードで確認してください。

## 公開後の検証

ビルド成功だけでは子プロセスの依存解決や実行を確認できません。実URLで画面を開き、各プロファイルの生成と正答・誤答の確認を行います。
`GET /api/catalog` の `hosting` と `limits.max_budget_seconds` が画面の説明・予算上限を決めます。
「未確認」や通信失敗を「解なし」「不正解」と読み替えないでください。

既存のヘッドレスブラウザテストは、明示したHTTPSのoriginに対しても実行できます。

```sh
cd apps/web
npm ci --ignore-scripts
npx playwright install chromium
PUZZLE_WEB_URL=https://YOUR_PRODUCTION_DOMAIN npm test
```

PowerShellでは先に `$env:PUZZLE_WEB_URL='https://YOUR_PRODUCTION_DOMAIN'` を設定します。
末尾のスラッシュやパスは付けません。この指定時はローカルサーバーを起動せず、実際の生成要求を送るため利用枠を消費します。
指定なしのCIは従来どおり専用のローカルサーバーを使い、外部デプロイや認証情報を必要としません。
検証時だけタイムアウト表示を固定応答で検査するケースがあり、プラットフォーム障害の再現試験ではありません。
