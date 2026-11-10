# AltContainer 統合ビルド

公式 AltStore Classic と StikDebug の最新リリースを6時間ごとに確認し、
最後に公開できたバージョンと異なる場合だけビルドします。失敗時は既存リリースを更新しません。
IPAは未署名です。自動ビルド成功は実機での互換性を保証しません。

## 配布ファイル

同じアーカイブから次の3ファイルを生成し、すべての生成・ZIP検査が成功した場合に
デフォルトブランチのビルドから `altcontainer-latest` リリースへ公開します。

- `LiveContainer.ipa`：内蔵ストアなしの単体版。
- `LiveContainer+SideStore.ipa`：従来のSideStore内蔵版。
- `AltContainer+StickDebug.ipa`：AltStore内蔵＋StikDebug同梱版。公開名は指定に合わせてStickDebugと表記。

PR・作業ブランチではActionsの成果物のみ保存し、リリースには公開しません。
自動ビルドは `altcontainer.yml` に一本化し、旧 `Xcode - Build` は手動実行の入口として保持します。

## 現在の対応範囲

- 元のLiveContainer／SideStoreビルド経路と証明書インポート処理は保持。
- 統合IPAでは内蔵ストアをAltStoreに変更。リンクメニューから3つのアカウントスロットを選択。
- 各スロットはデータ・仮想App Group・キーチェーンを分離。認証はAltStore内で実施。
  Apple IDのパスワードを独自の設定ファイルには保存しません。
- フィルターメニューのStikDebugは同梱IPAを通常のゲストアプリとして初回インストール。
  LiveContainerの署名証明書、ペアリングファイル、VPNなど従来の前提条件は必要です。
- AltStoreのiPad向けデバイス宣言・画面回転宣言を追加。レイアウトの完全対応は実機未確認です。
- 日本語リソースは `.github/altcontainer/localizations` に保持。

## 制限・未実装

- 任意のゲストIPAのウィジェットをホーム画面に登録する機能は未実装です。
  ゲスト内の `.appex` はiOSに自動登録されず、App IDの取得だけでは動きません。
  ホスト配下の拡張として再構成し、適合するプロファイル・App Groupで署名する必要があります。
- インストール用とウィジェット用でApple IDを分けて拡張を署名する機能は未実装です。
  プロビジョニングの整合性を無視して別チームのプロファイルを混在させません。
- AltStore v2.3のRemote AltServer機能を保持します。公式にはPCなしのインストール・更新・有効化に対応しています。
  AltStore設定の「Set up Remote AltServer」からのセットアップが必要です。内蔵環境での接続・更新は実機未検証です。
- AltStore専用の証明書読み出しは現在選択中のスロットが対象です。
- 3スロットは同時実行ではなく切り替え式です。新規ゲストには125〜127のキーチェーングループを割り当てません。
  既存インストールから移行する場合、それらのグループを利用しているゲストがないか確認が必要です。
- バイナリのハードコードされた英文やStoryboard全体を翻訳するものではありません。
- 元のSideStoreのクラッシュ原因は実機クラッシュログなしでは特定できません。

## ローカル検証

```sh
python3 -m unittest discover -s .github/altcontainer/tests -v
python3 .github/altcontainer/upstream.py --output upstream.json --download upstream
```

`package.py` は明示的に指定したホストアプリと2本のIPAだけを入力にします。
元のIPAは変更しません。暗号化、Bundle IDの不一致、危険なZIPパスは拒否します。
