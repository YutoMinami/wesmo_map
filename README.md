# WESMO!がつかえるお店・サービス マップ（一部のみ）

GitHub Pages で公開する前提の、静的な地図アプリです。

保留中の改善項目は [TODO.md](/home/yminami/workdir/wesmo_map/TODO.md) にまとめています。

## 構成

- `index.html`: 1ページのUI
- `styles.css`: レイアウトと見た目
- `app.js`: 現在地取得、距離計算、地図描画
- `data/chains_master.csv`: 対象チェーンの定義
- `data/shops_manual.csv`: 手入力と手修正の正本
- `data/shops_scraped.csv`: 将来の自動取得用プレースホルダ
- `data/shops_raw.csv`: 現在は手入力中心の中間データ
- `data/shops_geocoded.csv`: 緯度経度付き店舗一覧
- `data/geocode_cache.csv`: 住所と座標のキャッシュ
- `data/geocode_unresolved.csv`: 未解決住所の一覧
- `data/shops.json`: フロントエンド配信用データ
- `data/_cache/`: HTMLスナップショットなどのローカルキャッシュ置き場。Git管理しない
- `data/smart_code/chains_latest.csv`: Smart Code 一覧ページから抽出した最新チェーン一覧

## データ運用フロー

1. `data/chains_master.csv` に対象チェーンを記入する
2. 手入力分を `data/shops_manual.csv` に入れる
3. 必要なら自動取得分を `data/shops_scraped.csv` に入れる
4. `data/shops_raw.csv` を作る
5. 住所から座標を取得して `data/shops_geocoded.csv` を作る
6. 公開用に `data/shops.json` へ変換する

## 編集ルール

- `data/shops_manual.csv` は人が直接編集する
- `data/shops_scraped.csv` は今は空のままにしている
- `data/shops_raw.csv` は生成物として扱い、直接編集しない
- 同じ `shop_id` が重なった場合は手入力側を優先する前提で運用する
- `payment_tags` は複数対応を見越して `|` 区切りで持てるようにしてある

### JSON変換

```bash
python scripts/build_shops_json.py
```

`data/shops_geocoded.csv` を読み込み、`data/shops.json` を更新します。
`lat/lng` が入っていない未解決行はスキップされるので、解決済みの店舗だけを先に公開できます。

### 店舗一覧マージ

```bash
python scripts/build_shops_raw.py
```

`data/shops_manual.csv` と `data/shops_scraped.csv` をマージして
`data/shops_raw.csv` を更新します。`shop_id` が重複した場合は手入力側を優先し、
`payment_tags` は両方を統合します。

### Smart Code チェーン一覧取得

```bash
python scripts/fetch_smart_code_shoplist.py
```

`https://www.smart-code.jp/shoplist/` の HTML を `data/_cache/smart_code/` に保存し、
チェーン一覧を `data/smart_code/chains_latest.csv` に抽出します。
HTML スナップショットは Git 管理しません。

### ジオコーディング

```bash
python scripts/geocode_shops.py
```

`data/shops_raw.csv` を読み込み、`data/geocode_cache.csv` を参照しながら
`data/shops_geocoded.csv` を更新します。
すでに `lat/lng` がある行はその座標を優先し、ジオコーディングしません。
既定では `jageocoder` の公開 RPC を使い、日本住所向けに検索します。
未解決の行は `data/geocode_unresolved.csv` に書き出されます。

未解決を手で直すときの流れ:

1. `data/geocode_unresolved.csv` で未解決行を確認する
2. 同じ `shop_id` の行を `data/shops_manual.csv` に追加する
3. `lat` と `lng` を手で記入する
4. `data/geocode_unresolved.csv` は編集しない
5. `python scripts/build_shops_raw.py`
6. `python scripts/geocode_shops.py`

`data/shops_manual.csv` は手修正の正本なので、同じ `shop_id` がある場合は manual 側が優先されます。

よく使う例:

```bash
python scripts/geocode_shops.py --dry-run
python scripts/geocode_shops.py --only-chain lawson
python scripts/geocode_shops.py --limit 20
python scripts/geocode_shops.py --skip-cache
python scripts/geocode_shops.py --provider nominatim
```

## CSVカラム

### `chains_master.csv`

- `chain_code`: 内部キー
- `chain_name`: 表示名
- `enabled`: 対象に含めるか
- `source_type`: `manual` / `scrape` / `api`
- `source_url`: 店舗一覧の取得元
- `notes`: 補足

### `shops_raw.csv`

- `shops_manual.csv` と `shops_scraped.csv` をマージした生成物
- 直接編集しない

- `shop_id`: 店舗キー
- `chain_code`: チェーンキー
- `chain_name`: チェーン表示名
- `shop_name`: 店舗名
- `address`: 住所
- `lat`: 緯度。既知なら入れる
- `lng`: 経度。既知なら入れる
- `payment_tags`: たとえば `smart_code` のような値を入れる
- `source_url`: 取得元ページ

### `shops_manual.csv`

- 手入力と手修正の正本
- カラムは `shops_raw.csv` と同じ

### `shops_scraped.csv`

- 将来の自動取得の出力先
- カラムは `shops_raw.csv` と同じ

### `shops_geocoded.csv`

- `shop_id`: 店舗キー
- `chain_code`: チェーンキー
- `chain_name`: チェーン表示名
- `shop_name`: 店舗名
- `address`: 住所
- `lat`: 緯度
- `lng`: 経度
- `payment_tags`: 対応決済タグ
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
