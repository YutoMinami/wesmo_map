# TODO

## UI / Performance

- 初期表示時の地図マーカー数を制限する
- 初期表示一覧の件数制限や「もっと見る」を入れる
- `Leaflet.markercluster` などでクラスタリングを導入する
- 店舗数が増えたときの描画性能を測る
- 現在地なしのときの表示方針をさらに詰める

## Data Pipeline

- チェーン自動取得スクリプトを追加する
- `chains_master.csv` の `source_type` ごとに取得処理を分ける
- Smart Code 側の店舗一覧取得方法を決める
- 一致確認で迷うチェーン名を生成AI APIで補助判定できるようにする
- `shops_scraped.csv` の更新フローを整理する
- `shops_manual.csv` と `shops_scraped.csv` の重複検出を強化する

## Geocoding

- 未解決住所の正規化ルールをさらに強化する
- 未解決行の再試行フローを追加する
- 手修正済み住所の運用ルールをもう少し明文化する
- provider 切替時の挙動を整理する
- `geocode_unresolved.csv` から manual 補完しやすい補助を追加する

## Future Scope

- `payment_tags` を前提に表示やフィルタを作る
- 将来 Smart Code 以外の対応種別を扱うか再検討する
- 外部データ取り込みを再開する場合は、ライセンスと利用規約を先に確認する

## Publishing

- GitHub Pages 公開手順を軽く簡略化する
- 解決済み件数が増えた時の公開フローを整理する
- `shops.json` 生成時のスキップ件数を公開前チェックに組み込む
