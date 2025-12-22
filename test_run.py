from wsgi import app

# デバッグモードで実行(環境変数に従います)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
