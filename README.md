# DAnime Downloader

d アニメストアから mp4 ファイルをダウンロードします

## 特徴

-   Widevine 対応
-   検索対応
-   まとめてダウンロード

## 前提条件

### 必要なソフトウェア

1. **Python 3.7+**
2. **FFmpeg** - 動画・音声の結合用
3. **mp4decrypt** (Bento4) - DRM コンテンツの復号化用

### Python ライブラリ

```bash
pip install pywidevine beautifulsoup4 requests tqdm
```

### 必要なファイル

-   `device.wvd` - Widevine デバイスファイル（L3 CDM）

## インストール

1. リポジトリをクローン：

```bash
git clone https://github.com/amania-Jailbreak/danime-downloader.git
cd danime-downloader
```

2. 依存関係をインストール：

```bash
pip install -r requirements.txt
```

3. 外部ツールをインストール：

**FFmpeg:**

-   Windows: `winget install ffmpeg`
-   macOS: `brew install ffmpeg`
-   Linux: `sudo apt install ffmpeg`

**mp4decrypt (Bento4):**

-   https://github.com/axiomatic-systems/Bento4 からダウンロード
-   実行可能ファイルを PATH に追加

4. Widevine デバイスファイル（`device.wvd`）を配置

## EXE ファイルのビルド

### 自動ビルド（GitHub Actions）

このリポジトリでは、GitHub Actions を使用して自動的に EXE ファイルをビルドします：

-   **プッシュ時**: `main`ブランチへのプッシュ時に自動ビルド
-   **タグ時**: `v*`タグ作成時にリリースを自動作成
-   **手動実行**: GitHub 上で手動実行も可能

ビルドされた EXE ファイルは以下からダウンロード可能：

-   Actions タブの「Artifacts」から
-   Releases ページ（タグ作成時）

### ローカルビルド

#### Windows

```cmd
# バッチファイルを実行
build.bat
```

#### Linux/macOS

```bash
# シェルスクリプトを実行
chmod +x build.sh
./build.sh
```

#### 手動ビルド

```bash
# 依存関係をインストール
pip install pyinstaller

# ビルド実行
pyinstaller DAnimeDownloader.spec

# 生成されたEXEファイル
# Windows: dist/DAnimeDownloader.exe
# Linux/macOS: dist/DAnimeDownloader
```

## 使用方法

### 基本的な使用方法

```bash
# エピソードをダウンロード（最高画質）
python main.py 22435001 -c "your_cookies_string"

# クッキーファイルから読み込み
python main.py 22435001 --cookies-file cookies.txt

# 指定した画質でダウンロード
python main.py 22435001 -c "cookies" -r 1280x720

# カスタム出力パス
python main.py 22435001 -c "cookies" -o "output.mp4"

# カスタムデバイスファイル
python main.py 22435001 -c "cookies" -d "custom.wvd"
```

### Jellyfin 対応

```bash
# Jellyfin形式のファイル命名でダウンロード
python main.py 22435001 -c "cookies" --jellyfin

# 作品全体をJellyfin形式でダウンロード
python main.py 22435 -c "cookies" --jellyfin

# シーズン2としてダウンロード
python main.py 22435001 -c "cookies" --jellyfin --season 2
```

Jellyfin オプションを使用すると以下の形式で保存されます：

-   ファイル名: `Title - S01E01 - Episode Title.mp4`
-   ディレクトリ構造: `output/Title/S01/`
-   シーズン番号は`--season`オプションで指定可能（デフォルト: 1）

### 情報取得

```bash
# 作品情報とエピソード一覧を取得
python main.py 22435 -c "cookies" --work-info

# エピソード詳細情報を取得
python main.py 22435001 -c "cookies" --episode-info

# 利用可能な画質を表示
python main.py 22435001 -c "cookies" --quality-info
```

### バッチダウンロード

```bash
# 作品全体をダウンロード
python main.py 22435 -c "cookies"
```

## パラメータ

### 必須パラメータ

-   `part_id` - パート/作品 ID（8 桁：エピソード、5 桁：作品全体）

### オプションパラメータ

| オプション           | 説明                      | 例                           |
| -------------------- | ------------------------- | ---------------------------- |
| `-c`, `--cookies`    | ブラウザのクッキー文字列  | `-c "session=abc123..."`     |
| `--cookies-file`     | クッキーファイルのパス    | `--cookies-file cookies.txt` |
| `-o`, `--output`     | 出力ファイルパス          | `-o "video.mp4"`             |
| `-r`, `--resolution` | 目標解像度                | `-r 1920x1080`               |
| `-d`, `--device`     | Widevine デバイスファイル | `-d device.wvd`              |
| `--work-info`        | 作品情報を表示            |                              |
| `--episode-info`     | エピソード情報を表示      |                              |
| `--quality-info`     | 利用可能画質を表示        |                              |
| `--jellyfin`         | Jellyfin 形式で命名       |                              |

## クッキーの取得方法

1. ブラウザで d アニメ にログイン
2. 開発者ツールを開く（F12）
3. Network タブを選択
4. 任意のページをリロード
5. リクエストヘッダーから Cookie をコピー

### クッキーファイルの形式

```
session=abc123; user_id=xyz789; auth_token=def456
```

## ファイル構造

```
DAnimePlus/
├── main.py              # メインスクリプト
├── device.wvd           # Widevineデバイスファイル
├── cookies.txt          # クッキーファイル（オプション）
├── requirements.txt     # Python依存関係
├── README.md           # このファイル
└── output/             # ダウンロードされた動画（自動作成）
    └── [作品名]/
        ├── 01_エピソード1.mp4
        ├── 02_エピソード2.mp4
        └── ...
```

## 対応画質

-   1920x1080 (フル HD)
-   1280x720 (HD)
-   852x480 (SD)
-   その他の利用可能な解像度

画質は`--quality-info`オプションで確認できます。

## エラーとトラブルシューティング

### よくあるエラー

1. **"Device file not found"**

    - `device.wvd`ファイルが存在することを確認
    - パスが正しいことを確認

2. **"No cookies provided"**

    - `-c`または`--cookies-file`オプションを使用
    - クッキーが有効であることを確認

3. **"MPD URL not found"**

    - ログインセッションが有効であることを確認
    - コンテンツが利用可能であることを確認

4. **"FFmpeg/mp4decrypt not found"**

    - 必要なツールがインストールされ、PATH に追加されていることを確認

5. **"PSSH not found"**
    - d アニ初期に追加されたアニメは PlayReady 方式で暗号化されていますが このツールは対応していません

### デバッグ

プログレスバーとエラーメッセージが詳細な情報を提供します。問題が発生した場合は、以下を確認してください：

1. インターネット接続
2. DAnime Store へのアクセス権限
3. 必要なファイルとツールの存在
4. クッキーの有効性

## 法的事項

-   d アニメストアは、KDDI 株式会社の商標です。
-   本ソフトウェアは KDDI 及び Docomo と関係がなく非公式なものです
-   著作権法を遵守してください
-   個人的な使用のみに留めてください

## 貢献

バグ報告や機能要求は、GitHub の Issues で受け付けています。
PlayReady の対応のリクエスト待ってます

## 免責事項

このソフトウェアの使用により生じるいかなる損害についても、開発者は責任を負いません。ユーザーの責任で使用してください。
