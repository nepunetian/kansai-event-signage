# 関西イベントサイネージ（自動収集版）

Fire TVなどのブラウザで常時表示するためのWebアプリです。

## 今回追加した機能
- 実在イベントを初期データとして収録
- Walkerplus関西イベントから自動収集する `update_events.py`
- 開催終了イベントを自動除外
- 鉄道 / AI・IT / XR / ガジェット / アニメ・ゲーム / 道の駅等を優先するスコアリング
- 取得失敗時に既存データを壊さない安全処理
- GitHub Actionsで毎朝自動更新
- Fire TV側はURLを開いたままで、15分ごとに更新データを再読込

## 一番簡単な公開方法: GitHub Pages

1. GitHubで新しいリポジトリを作る
2. このフォルダの中身をアップロードする
3. Settings → Pages → Deploy from a branch → `main` / root を選択
4. 発行されたURLをFire TVブラウザで開く
5. Settings → Actions → General → Workflow permissions を
   `Read and write permissions` にする

GitHub Actionsが日本時間の毎朝6:10頃にイベント一覧を更新します。
手動更新したい場合は Actions → Update Kansai Events → Run workflow。

## PCで自動収集を試す

    pip install -r requirements.txt
    python update_events.py
    python -m http.server 8080

ブラウザ:
    http://localhost:8080

## 好みを変える
`config.json` の `interest_keywords` の数字を変更してください。
数字が大きいほどサイネージ上位に出やすくなります。

例:
    "鉄道": 25
    "AI": 24
    "道の駅": 25

## 注意
イベント情報サイトのHTML構造が将来変更された場合は、
`update_events.py` の解析部分を調整する必要があります。
イベント開催状況は主催者の公式情報も確認してください。
