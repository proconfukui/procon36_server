import socket
import threading
import time
import requests
import signal
import sys

match_info = None # 接続してきたクライアント全員に配布する試合情報
best_solution = None # これまでに受け取った最も良い解
lock = threading.Lock() # best_solutionやmatch_infoを安全に更新するためのロック
server_socket = None # サーバーソケットのグローバル参照

API_URL = "http://localhost:3000" # 競技サーバー用APIのURL
TOKEN = "player1" # 認証トークン

# 2つの解を比較して、良い方を返す
def get_better_solution(sol1, sol2):
    if sol1 is None:
        return sol2
    if sol2 is None:
        return sol1

    # ペア数を比較
    sol1_pair_count = 0
    if "pair_count" in sol1:
        sol1_pair_count = sol1.pop("pair_count")
    sol2_pair_count = 0
    if "pair_count" in sol2:
        sol2.pop("pair_count")
    if sol1_pair_count > sol2_pair_count:
        return (sol1, sol1_pair_count)
    if sol1_pair_count < sol2_pair_count:
        return (sol2, sol2_pair_count)

    # ペア数が同じ場合は手数を比較
    if len(sol1.get("ops", [])) < len(sol2.get("ops", [])):
        return (sol1, sol1_pair_count)

    return (sol2, sol2_pair_count)

# クライアントからの接続を処理する
def handle_client(conn, addr):
    print(f"新しい接続を確認：{addr}")
    try:
        # まず試合情報をクライアントに送信
        with lock:
            if match_info:
                match_data = json.dumps(match_info).encode("utf-8")
                conn.sendall(match_data)
                print(f"{addr} に試合情報を送信")
            else:
                print("エラー：試合情報が利用できません")
                return
        
        # 接続を閉じてクライアントに送信完了を通知
        conn.shutdown(socket.SHUT_WR)
        
        # クライアントからデータを受信 (1024バイトずつ)
        data = b""
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            data += chunk

        if data:
            # 受信したデータをJSONとしてパース
            solution = json.loads(data.decode("utf-8"))
            print(f"{addr} から解を受信")

            # グローバル変数へのアクセスをロック
            with lock:
                global best_solution
                # 現在の最良解と比較
                new_best, pair_count = get_better_solution(best_solution, solution)

                if new_best is not best_solution:
                    best_solution = new_best
                    print(f"提出解を更新（ペア数：{pair_count}、手数：{len(best_solution.get('ops', []))}）")
                    print("回答を提出...")
                    # 本番サーバーへ提出（認証付き）
                    headers = {"Procon-Token": TOKEN}
                    responce = requests.post(f"{API_URL}/", json=best_solution, headers=headers)
                    match responce.status_code:
                        case 200:
                            json = responce.json()
                            revision = json.get("revision", -1)
                            print(f"回答が受理された。受理番号：{revision}")
                        case 400:
                            print("エラー：リクエストの内容が不正")
                        case 401:
                            print("エラー：トークンが指定されていないか不正")
                        case 403:
                            print("エラー：競技時間外にアクセス")
                        case _:
                            print("エラー：予期しないエラー")
    except Exception as e:
        print(f"エラー：{e}")
    finally:
        conn.close()
        print(f"接続を切断：{addr}")

# 競技サーバーから試合情報を取得し、グローバル変数に格納する
def fetch_match_info():
    global match_info
    while True:
        try:
            print(f"{API_URL}/ から試合情報を取得...")
            # 競技サーバーの / エンドポイントにGETリクエストを送信（認証付き）
            headers = {"Procon-Token": TOKEN}
            response = requests.get(f"{API_URL}/", headers=headers)
            response.raise_for_status() # エラーがあれば例外を発生させる

            data = response.json()
            
            with lock:
                match_info = data
            
            print("試合情報の取得に成功")
            # 試合開始時刻まで待機
            wait_for_match_start(match_info)
            return

        except requests.exceptions.RequestException as e:
            print(f"試合情報の取得に失敗：{e}")
            print("5秒後に再試行...")
            time.sleep(5)

# 試合開始時刻まで待機する
def wait_for_match_start(info):
    start_at_unix = info.get("startsAt", 0)
    current_unix = int(time.time())
    
    wait_time = start_at_unix - current_unix
    
    if wait_time > 0:
        print(f"試合開始まで{wait_time}秒...")
        time.sleep(wait_time)
    
    print("試合開始！")

# シグナルハンドラ（Ctrl+Cなどで終了時にソケットを適切に閉じる）
def signal_handler(sig, frame):
    global server_socket
    print("\nサーバーを終了しています...")
    if server_socket:
        server_socket.close()
        print("サーバーソケットを閉じました")
    sys.exit(0)

def main():
    global server_socket
    
    # シグナルハンドラを登録（Ctrl+C、SIGTERMなど）
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # サーバー起動時に一度だけ試合情報を取得
    fetch_match_info()

    HOST = "0.0.0.0"  # 全てのインターフェースでリスニング
    PORT = 8888  # ポート9999が使用中のため8888に変更
    
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # ソケットの再利用を許可（Address already in useエラーを防ぐ）
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"チームのサーバーが {HOST}:{PORT} でリスニング中")

        while True:
            try:
                conn, addr = server_socket.accept()
                thread = threading.Thread(target=handle_client, args=(conn, addr))
                thread.daemon = True  # メインスレッド終了時に子スレッドも終了
                thread.start()
            except OSError:
                # ソケットが閉じられた場合（正常終了）
                break
                
    except Exception as e:
        print(f"サーバーエラー: {e}")
    finally:
        # リソースのクリーンアップ
        if server_socket:
            server_socket.close()
            print("サーバーソケットを閉じました")

if __name__ == "__main__":
    main()
