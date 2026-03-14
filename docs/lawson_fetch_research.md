# Lawson 店舗URL収集メモ

更新日: 2026-03-14

## 現状の観察

- Lawson の店舗検索トップは都道府県リンクを持つ
- 店舗詳細ページは `https://www.e-map.ne.jp/p/lawson/dtl/<id>/` 形式
- `<id>` は疎な番号体系に見える
- そのため `dtl/<id>` の総当たりは第一候補にしない

確認できた例:

- `https://www.e-map.ne.jp/p/lawson/`
- `https://www.e-map.ne.jp/p/lawson/dtl/101505/`
- `https://www.e-map.ne.jp/p/lawson/dtl/217610/`
- `https://www.e-map.ne.jp/p/lawson/dtl/364156/`

## 推奨方針

1. 店舗本体のスクレイピングより先に、店舗詳細URLの列挙方法を確定する
2. まず検索UIが内部で叩いている XHR / API を確認する
3. それが無ければ都道府県別導線から店舗URLを収集する
4. `dtl/<id>` 総当たりは最後の手段にする

## 次に確認すること

- 都道府県リンク先の URL パターン
- 市区町村やフリーワード検索時の XHR
- 一覧ページに店舗詳細URLが埋まっているか
- 一覧ページにページネーションや件数上限があるか

## 注意

`e-map.ne.jp` の地図利用規約には、地図データの複製・抽出・加工などの制限がある。
地図そのものではなく、店舗ページの公開情報から必要最小限の店舗属性だけを扱う前提でも、
公開用データソースにする前に運用上の妥当性は再確認した方がよい。

## 参考

- Lawson 店舗検索トップ: https://www.e-map.ne.jp/p/lawson/
- e-map Terms of Use for Map: https://support.e-map.ne.jp/files/v3/Terms_of_Use_for_Map_en.pdf
