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
- `shops_scraped.csv` の更新フローを整理する
- `shops_manual.csv` と `shops_scraped.csv` の重複検出を強化する

## Geocoding

- 未解決住所の正規化ルールをさらに強化する
- 未解決行の再試行フローを追加する
- 手修正済み住所の運用ルールをもう少し明文化する
- provider 切替時の挙動を整理する
- `geocode_unresolved.csv` から manual 補完しやすい補助を追加する

## BLUE tag / Smart Code

- `payment_tags` を前提に表示やフィルタを作る
- Smart Code と BLUE tag の両対応店舗をどう表現するか決める
- BLUE tag My Maps 取り込みの説明文依存部分を必要なら調整する
- My Maps エクスポート更新時の運用手順を整理する

## Publishing

- GitHub Pages 公開手順を軽く簡略化する
- 解決済み件数が増えた時の公開フローを整理する
- `shops.json` 生成時のスキップ件数を公開前チェックに組み込む
