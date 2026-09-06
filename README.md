# 関西イベントサイネージ（X対応版）

Fire TVのブラウザで常時表示する個人向けイベントサイネージです。

## 収集対象
- Walkerplus 関西イベント
- X の直近投稿（X APIのBearer Tokenを設定した場合）

## 優先ジャンル
- 鉄道
- AI / IT / XR / ガジェット
- アニメ / マンガ / 声優 / コスプレ
- ゲーム
- 食 / グルメ / ラーメン / カレー / スイーツ / パン / フードフェス
- 展示会

「道の駅」は個人向け推薦から除外しています。

## X APIを有効にする
X Developer Consoleで利用可能なBearer Tokenを用意します。

GitHub:
1. リポジトリ → Settings
2. Secrets and variables → Actions
3. New repository secret
4. Name: `X_BEARER_TOKEN`
5. Secret: Bearer Tokenを貼り付け
6. Add secret

Bearer Tokenは `config.json` や `app.js` に直接書かないでください。

## 手動更新
GitHub → Actions → Update Kansai Events → Run workflow

## 自動更新
GitHub Actionsで毎朝6:10（日本時間）に更新します。

## Xの検索内容
`config.json` の `x_queries` で変更できます。
現在は、関西の一般イベント・アニメ/ゲーム・食/グルメ・鉄道・AI/ガジェットを検索します。

X投稿からイベントとして採用するのは、開催日（例: 9/20、9月20日）が本文に明記されている投稿だけです。
誤検出を減らすための仕様です。
