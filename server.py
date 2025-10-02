import socket
import threading
import time
import requests
import signal
import sys
import json
from typing import Dict, Any, Optional, Tuple, Union
import types
import copy

match_info: Optional[Dict[str, Any]] = None # 接続してきたクライアント全員に配布する試合情報
best_solution: Optional[Dict[str, Any]] = None # これまでに受け取った最も良い解
best_pair_count: int = 0 # 最も良い解のペア数
best_ops_count: int = 0 # 最も良い解の手数
lock: threading.Lock = threading.Lock() # best_solutionやmatch_infoを安全に更新するためのロック
server_socket: Optional[socket.socket] = None # サーバーソケットのグローバル参照
new_best_solution_event = threading.Event() # 新しい最良解が見つかったことをメインスレッドに知らせるためのイベント

API_URL: str = "http://localhost:3000" # 競技サーバー用APIのURL
TOKEN: str = "player1" # 認証トークン

# 2つの解を比較して、良い方を返す
def get_better_solution(sol1: Optional[Dict[str, Any]], sol2: Optional[Dict[str, Any]]) -> Union[Optional[Dict[str, Any]], Tuple[Dict[str, Any], int]]:
    if sol1 is None:
        sol2_pair_count: int = sol2.get("pair_count") if "pair_count" in sol2 else 0
        return (sol2, sol2_pair_count)
    if sol2 is None:
        sol1_pair_count: int = sol1.get("pair_count") if "pair_count" in sol1 else 0
        return (sol1, sol1_pair_count)

    # ペア数を比較
    sol1_pair_count: int = sol1.get("pair_count") if "pair_count" in sol1 else 0
    sol2_pair_count: int = sol2.get("pair_count") if "pair_count" in sol2 else 0
    if sol1_pair_count > sol2_pair_count:
        return (sol1, sol1_pair_count)
    if sol1_pair_count < sol2_pair_count:
        return (sol2, sol2_pair_count)

    # ペア数が同じ場合は手数を比較
    if len(sol1.get("ops", [])) < len(sol2.get("ops", [])):
        return (sol1, sol1_pair_count)

    return (sol2, sol2_pair_count)

# クライアントからの接続を処理する
def handle_client(conn: socket.socket, addr: Tuple[str, int]) -> None:
    print(f"新しい接続を確認：{addr}")
    try:
        # まず試合情報をクライアントに送信
        with lock:
            if match_info:
                match_data: bytes = json.dumps(match_info).encode("utf-8")
                conn.sendall(match_data)
                print(f"{addr} に試合情報を送信")
            else:
                print("エラー：試合情報が利用できません")
                return
        
        # 接続を閉じてクライアントに送信完了を通知
        conn.shutdown(socket.SHUT_WR)
        
        # クライアントからデータを受信 (1024バイトずつ)
        data: bytes = b""
        while True:
            chunk: bytes = conn.recv(1024)
            if not chunk:
                break
            data += chunk

        if data:
            # 受信したデータをJSONとしてパース
            solution: Dict[str, Any] = json.loads(data.decode("utf-8"))
            print(f"{addr} から解を受信")

            # グローバル変数へのアクセスをロック
            with lock:
                global best_solution, best_pair_count, best_ops_count
                # 現在の最良解と比較
                result = get_better_solution(best_solution, solution)
                pair_count: int = 0
                if isinstance(result, tuple):
                    new_best, pair_count = result
                else:
                    new_best, pair_count = result, 0
                ops_count = len(new_best.get('ops', [])) if new_best else 0

                if new_best is not best_solution:
                    best_solution = new_best
                    best_pair_count = pair_count
                    best_ops_count = ops_count
                    print(f"\r{' '*80}\r", end='') # 現在の行をクリア
                    print(f"新しい最良解が見つかりました！（ペア数={pair_count}、手数={ops_count}）")
                    print("コマンド > ", end='', flush=True) # プロンプトを再表示
                else:
                    print(f"{addr} の解は最良解ではありません")
    except Exception as e:
        print(f"エラー：{e}")
    finally:
        conn.close()
        print(f"接続を切断：{addr}")

# 競技サーバーから試合情報を取得し、グローバル変数に格納する
def fetch_match_info() -> None:
    global match_info
    while True:
        try:
            print(f"{API_URL}/ から試合情報を取得...")
            # 競技サーバーの / エンドポイントにGETリクエストを送信（認証付き）
            headers: Dict[str, str] = {"Procon-Token": TOKEN}
            response: requests.Response = requests.get(f"{API_URL}/", headers=headers)
            response.raise_for_status() # エラーがあれば例外を発生させる

            data: Dict[str, Any] = response.json()
            
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

# 人間が承認した解を競技サーバーに提出する（認証付き）
def submit_to_official_server(solution_to_submit):
    if not match_info:
        print("エラー：試合情報が利用できません")
        return
    
    print("回答を提出...")
    headers: Dict[str, str] = {"Procon-Token": TOKEN}
    responce: requests.Response = requests.post(f"{API_URL}/", json=solution_to_submit, headers=headers)
    match responce.status_code:
        case 200:
            response_data: Dict[str, Any] = responce.json()
            revision: int = response_data.get("revision", -1)
            print(f"回答が受理された（受理番号：{revision}）")
        case 400:
            print("エラー：リクエストの内容が不正")
        case 401:
            print("エラー：トークンが指定されていないか不正")
        case 403:
            print("エラー：競技時間外にアクセス")
        case _:
            print("エラー：予期しないエラー")

# 試合開始時刻まで待機する
def wait_for_match_start(info: Dict[str, Any]) -> None:
    start_at_unix: int = info.get("startsAt", 0)
    current_unix: int = int(time.time())
    
    wait_time: int = start_at_unix - current_unix
    
    if wait_time > 0:
        print(f"試合開始まで{wait_time}秒...")
        time.sleep(wait_time)
    
    print("試合開始！！")

# シグナルハンドラ（Ctrl+Cなどで終了時にソケットを適切に閉じる）
def signal_handler(sig: int, frame: Optional[types.FrameType]) -> None:
    global server_socket
    print("\nサーバーを終了しています...")
    if server_socket:
        server_socket.close()
        print("サーバーソケットを閉じました")
    sys.exit(0)

# クライアントからの接続を待ち受けるループを動かすスレッド
def start_server_listener():
    HOST: str = "0.0.0.0"  # 全てのインターフェースでリスニング
    PORT: int = 8888  # ポート9999が使用中のため8888に変更
    
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # ソケットの再利用を許可（Address already in useエラーを防ぐ）
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen()
        print(f"チームのサーバーが {HOST}:{PORT} でリスニング中")

        while True:
            try:
                conn: socket.socket
                addr: Tuple[str, int]
                conn, addr = server_socket.accept()
                thread: threading.Thread = threading.Thread(target=handle_client, args=(conn, addr))
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

def print_help():
    print("\n利用可能なコマンド：")
    print("  submit: 現時点の最良解を競技サーバーに提出する。")
    print("  status: 現時点の最良解のペア数と手数を表示する。")
    print("  help  : この説明を表示する。")
    print("  exit  : プログラムを終了する。")

# ユーザーからの入力を担当するメイン関数
def main() -> None:
    global server_socket, match_info, best_solution
    
    # シグナルハンドラを登録（Ctrl+C、SIGTERMなど）
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # サーバー起動時に一度だけ試合情報を取得
    fetch_match_info()
    if not match_info:
        print("試合情報の取得に失敗したため、サーバーを起動できません")
        return
    
    # サーバーの待ち受け処理をバックグラウンドで開始
    listener_thread = threading.Thread(target=start_server_listener, daemon=True)
    listener_thread.start()

    print_help()
    print("クライアントから解の受信を待機中...")
    while True:
        try:
            # ユーザーからのコマンド入力を待つ
            user_input = input("\nコマンド > ").lower().strip()
            match user_input:
                case "submit":
                    if best_solution is None:
                        print("\n最良解はまだ受信されていません")
                        continue
                    # 提出中にbest_solutionが更新されないようにディープコピー
                    solution_for_submission = copy.deepcopy(best_solution)
                
                    submit_to_official_server(solution_for_submission)
                case "status":
                    with lock:
                        if best_solution is None:
                            print("\n最良解はまだ受信されていません")
                        else:
                            print(f"\n現在の最良解：ペア数={best_pair_count}、手数={best_ops_count}")
                case "help":
                    print_help()
                case "exit":
                    print("\nプログラムを終了します...")
                    break
                case _:
                    print("\n不明なコマンドです。'help' コマンドで利用可能なコマンドを確認してください。")
        except EOFError: # Ctrl+Dなどで入力が終わった場合
            print("\nプログラムを終了...")
            return

if __name__ == "__main__":
    main()
