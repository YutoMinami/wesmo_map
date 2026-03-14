# WESMO!がつかえるお店・サービス マップ（一部のみ）

GitHub Pages で公開する前提の、静的な地図アプリです。

保留中の改善項目は [TODO.md](/home/yminami/workdir/wesmo_map/TODO.md) にまとめています。

現在の設計上の論点:

- `app.js` は住所検索、地図描画、一覧描画を1ファイルで持っているため、今後のUI追加時には分割を検討する
- `geocode_shops.py` にはチェーン別の住所正規化戦略があり、チェーン追加時には個別ロジックを汎用処理へ埋め込まずに切り出す
- `chains_master.csv` の列追加時は、関連スクリプト全体が新スキーマに追従しているか確認する

## 構成

- `index.html`: 1ページのUI
- `styles.css`: レイアウトと見た目
- `app.js`: 現在地取得、距離計算、地図描画
- `data/chains_master.csv`: 対象チェーンの定義
- `data/category_master.csv`: 表示用カテゴリの定義
- `data/shops_manual.csv`: 手入力と手修正の正本
- `data/shops_scraped.csv`: 将来の自動取得用プレースホルダ
- `data/shops_raw.csv`: 現在は手入力中心の中間データ
- `data/shops_geocoded.csv`: 緯度経度付き店舗一覧
- `data/geocode_cache.csv`: 住所と座標のキャッシュ
- `data/geocode_unresolved.csv`: 未解決住所の一覧
- `data/shops.json`: フロントエンド配信用データ
- `data/_cache/`: HTMLスナップショットなどのローカルキャッシュ置き場。Git管理しない
- `data/smart_code/chains_latest.csv`: Smart Code 一覧ページから抽出した最新チェーン一覧
- `data/smart_code/chain_aliases.csv`: Smart Code表記と手元マスタ表記の対応表
- `data/smart_code/chains_review_latest.csv`: 一致確認が必要なチェーン一覧
- `data/smart_code/chains_fetch_queue_latest.csv`: 店舗取得に進めるチェーン一覧
- `data/smart_code/chains_fetch_blocked_latest.csv`: 店舗取得前に手確認が必要なチェーン一覧
- `data/smart_code/lawson_shop_urls_latest.csv`: Lawson 店舗URL収集の作業ファイル
- `data/smart_code/nishimatsuya_shops_latest.csv`: 西松屋の取得結果
- `data/smart_code/nishimatsuya_closed_latest.csv`: 西松屋の閉店店舗一覧
- `docs/lawson_fetch_research.md`: Lawson 店舗URL収集の調査メモ

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

### Smart Code チェーン差分

```bash
python scripts/diff_smart_code_chains.py
```

`data/smart_code/chains_latest.csv` と `data/smart_code/chains_previous.csv` を比較し、
追加・削除されたチェーンを `data/smart_code/chain_changes_latest.csv` に出力します。

### チェーンマスタ更新

```bash
python scripts/update_chains_master.py
```

`data/smart_code/chains_latest.csv` と `data/smart_code/chain_changes_latest.csv` をもとに
`data/chains_master.csv` を更新します。

- Smart Code 上で観測中の既存チェーンは `last_seen_at` を更新
- 新規チェーンは `enabled=FALSE`、`source_type=review_needed` で追加
- 一覧から消えた既存チェーンは `deleted_at` を付与
- `notes` や既存の `enabled` は維持
- `data/smart_code/chain_aliases.csv` にある表記ゆれは吸収する
- `data/smart_code/chains_review_latest.csv` に未一致チェーンを出す

### 店舗取得キュー生成

```bash
python scripts/build_chain_fetch_queue.py
```

Smart Code で変化があったチェーンを `chains_master.csv` と突き合わせて、
店舗取得に進めるチェーンを `data/smart_code/chains_fetch_queue_latest.csv` に、
まだ確認が必要なチェーンを `data/smart_code/chains_fetch_blocked_latest.csv` に出力します。

### Lawson URL収集

```bash
python scripts/fetch_lawson_shop_urls.py
```

Lawson は一覧導線が複雑なので、まず店舗詳細URLの収集を独立した段階として扱います。
現状は雛形のみで、次の調査対象は以下です。

- 検索UIが内部で叩いている XHR / API
- 都道府県や市区町村の一覧導線
- `dtl/<id>` の総当たり以外で全件を列挙できる手段

調査メモは [docs/lawson_fetch_research.md](/home/yminami/workdir/wesmo_map/docs/lawson_fetch_research.md) に残しています。

### 西松屋 店舗取得

```bash
python scripts/fetch_nishimatsuya_shops.py
```

`https://www.24028.jp/tenpo/shoplist.php?cid=<都道府県番号>` を全件取得して、
`data/smart_code/nishimatsuya_shops_latest.csv` を更新します。
閉店と判断した店舗は `data/smart_code/nishimatsuya_closed_latest.csv` に分けて保存し、
`data/shops_scraped.csv` には入れません。
同時に `data/shops_scraped.csv` の `chain_code=nishimatsuya` 行を置き換えます。

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
python scripts/geocode_shops.py --only-chain nishimatsuya --offset 200 --limit 200
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
- `source_tags`: `smart_code_site|wesmo_site` のような出所タグ
- `source_category`: Smart Code や Wesmo! 一覧など元データ上のカテゴリ名
- `category`: UI 用に正規化したカテゴリコード
- `payment_tags`: `smart_code|wesmo|blue_tag` のような対応区分
- `first_seen_at`: 最初に確認した日
- `last_seen_at`: 直近で確認した日
- `deleted_at`: 一覧から消えたと判断した日
- `notes`: 補足

### `category_master.csv`

- `category`: UI 用のカテゴリコード
- `label_ja`: フィルタに出す日本語ラベル
- `description`: 補足

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
- 住所・駅名検索は `app.js` の provider 切替で `GSI` / `Nominatim` を選べる
- `1km / 3km / 5km` の半径切替
- Leaflet + OpenStreetMap で地図表示
- 静的JSONから加盟店データを読み込み
- 距離順のリスト表示

## 公開方法

1. このリポジトリを GitHub に push
2. GitHub Pages を branch 配信で有効化
3. ルートディレクトリを配信対象に設定
