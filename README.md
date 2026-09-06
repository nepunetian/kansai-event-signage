# 関西イベントサイネージ（フルHD画像版）

Fire TV のブラウザ向けに、**1920x1080 の1画面で情報が収まる**ように調整した版です。

## 今回の変更
- フルHD 1画面固定レイアウト
- ページ全体のスクロールなし
- 左側に注目イベントの大きな画像表示
- 右側にイベントカード6件を画像付きで表示
- 注目イベントは12秒ごとに切替
- 右側一覧は16秒ごとにページ切替
- `events.json` に `image_url` を持てるよう変更
- `update_events.py` でイベント画像URLも収集
- 画像がない場合は `placeholder.svg` を表示

## 画像の取得元
- Walkerplus のイベント詳細ページの JSON-LD `image`
- 取れない場合は `og:image`
- X は添付画像がある投稿のみ `image_url` を取得

## GitHub への更新
1. ZIPを解凍
2. ローカルの `kansai-event-signage` フォルダへ上書き
3. GitHub Desktop で Commit
4. Push origin

## Fire TV での使い方
公開URLを開くだけです。画面全体は固定で、注目イベントと一覧だけが自動切替します。
