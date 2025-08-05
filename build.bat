@echo off
echo Building DAnime Downloader executable...

:: 仮想環境をアクティベート（存在する場合）
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    echo Virtual environment activated
)

:: 依存関係をインストール
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

:: PyInstallerでビルド
echo Building executable...
pyinstaller DAnimeDownloader.spec

:: ビルド完了の確認
if exist dist\DAnimeDownloader.exe (
    echo.
    echo Build completed successfully!
    echo Executable created: dist\DAnimeDownloader.exe
    echo.
    
    :: 簡単なテスト
    echo Testing executable...
    dist\DAnimeDownloader.exe --help
    
    echo.
    echo Build and test completed!
) else (
    echo.
    echo Build failed! Please check the error messages above.
    exit /b 1
)

pause
