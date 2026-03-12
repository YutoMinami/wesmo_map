# Smart Code加盟店マップ

GitHub Pages で公開する前提の、静的な地図アプリです。

## 構成

- `index.html`: 1ページのUI
- `styles.css`: レイアウトと見た目
- `app.js`: 現在地取得、距離計算、地図描画
- `data/chains_master.csv`: 対象チェーンの定義
- `data/shops_raw.csv`: 店舗一覧の中間データ
- `data/shops_geocoded.csv`: 緯度経度付き店舗一覧
- `data/shops.json`: フロントエンド配信用データ

## データ運用フロー

1. `data/chains_master.csv` に対象チェーンを記入する
2. 店舗一覧を取得して `data/shops_raw.csv` を作る
3. 住所から座標を取得して `data/shops_geocoded.csv` を作る
4. 公開用に `data/shops.json` へ変換する

### JSON変換

```bash
python scripts/build_shops_json.py
```

`data/shops_geocoded.csv` を読み込み、`data/shops.json` を更新します。

## CSVカラム

### `chains_master.csv`

- `chain_code`: 内部キー
- `chain_name`: 表示名
- `enabled`: 対象に含めるか
- `source_type`: `manual` / `scrape` / `api`
- `source_url`: 店舗一覧の取得元
- `notes`: 補足

### `shops_raw.csv`

- `shop_id`: 店舗キー
- `chain_code`: チェーンキー
- `chain_name`: チェーン表示名
- `shop_name`: 店舗名
- `address`: 住所
- `source_url`: 取得元ページ

### `shops_geocoded.csv`

- `shop_id`: 店舗キー
- `chain_code`: チェーンキー
- `chain_name`: チェーン表示名
- `shop_name`: 店舗名
- `address`: 住所
- `lat`: 緯度
- `lng`: 経度
- `source_url`: 取得元ページ

## MVPの機能

- ブラウザの Geolocation API で現在地取得
- `1km / 3km / 5km` の半径切替
- Leaflet + OpenStreetMap で地図表示
- 静的JSONから加盟店データを読み込み
- 距離順のリスト表示

## 公開方法

1. このリポジトリを GitHub に push
2. GitHub Pages を branch 配信で有効化
3. ルートディレクトリを配信対象に設定
