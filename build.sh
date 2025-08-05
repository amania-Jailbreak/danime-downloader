#!/bin/bash

echo "Building DAnime Downloader executable..."

# 仮想環境をアクティベート（存在する場合）
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    echo "Virtual environment activated"
fi

# 依存関係をインストール
echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# PyInstallerでビルド
echo "Building executable..."
pyinstaller DAnimeDownloader.spec

# ビルド完了の確認
if [ -f "dist/DAnimeDownloader" ]; then
    echo ""
    echo "Build completed successfully!"
    echo "Executable created: dist/DAnimeDownloader"
    echo ""
    
    # 実行権限を付与
    chmod +x dist/DAnimeDownloader
    
    # 簡単なテスト
    echo "Testing executable..."
    ./dist/DAnimeDownloader --help
    
    echo ""
    echo "Build and test completed!"
else
    echo ""
    echo "Build failed! Please check the error messages above."
    exit 1
fi
