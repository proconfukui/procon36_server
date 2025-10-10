# ベースとなる軽量なLinuxイメージを指定
FROM ubuntu:22.04

# コンテナ内の作業ディレクトリを作成・指定
WORKDIR /app

# ホスト（Mac）からコンテナへサーバーの実行ファイルをコピー
COPY procon36_server_linux_amd64 .

# 実行ファイルに実行権限を付与
RUN chmod +x ./procon36_server_linux_amd64

# サーバーが使用するポートを公開
EXPOSE 3000

# コンテナのメインプログラムを指定
ENTRYPOINT ["./procon36_server_linux_amd64"]

# ENTRYPOINTに渡すデフォルトの引数を指定
CMD ["-listen", ":3000", "-config", "match.json"]
