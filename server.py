import socket
import json
import threading

# これまでに受け取った最も良い解を保存する変数
best_solution = None
# best_solutionを更新する際に複数のスレッドが同時にアクセスしないようにするためのロック
lock = threading.Lock()

# 競技ルールに基づいて2つの解を比較する関数
def get_better_solution(sol1, sol2):
    """
    2つの解を比較し、より良い方とそのペア数を返す。
    ルール: 1. ペア数が多い方 / 2. 手数が少ない方
    """
    if sol1 is None:
        return sol2
    if sol2 is None:
        return sol1

    # ペア数を比較
    sol1_pair_count = sol1.pop("pair_count")
    sol2_pair_count = sol2.pop("pair_count")
    if sol1_pair_count > sol2_pair_count:
        return (sol1, sol1_pair_count)
    if sol1_pair_count < sol2_pair_count:
        return (sol2, sol2_pair_count)

    # ペア数が同じ場合は手数を比較
    if len(sol1.get("ops", [])) < len(sol2.get("ops", [])):
        return (sol1, sol1_pair_count)

    return (sol2, sol2_pair_count)

# 各クライアントからの接続を処理する関数
def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")
    try:
        # クライアントからデータを受信 (1024バイトずつ)
        data = b""
        while True:
            chunk = conn.recv(1024)
            if not chunk:
                break
            data += chunk

        if data:
            # 受信したデータをJSONとしてパース
            solution = json.loads(data.decode('utf-8'))
            print(f"Received solution from {addr}")

            # グローバル変数へのアクセスをロック
            with lock:
                global best_solution
                # 現在の最良解と比較
                new_best, pair_count = get_better_solution(best_solution, solution)

                if new_best is not best_solution:
                    best_solution = new_best
                    print("--- [UPDATE] New best solution found! ---")
                    print(f"  Pairs: {pair_count}, Rotations: {len(best_solution.get('ops', []))}")
                    # TODO: ここに本番サーバーへ提出する処理を追加する
                    # submit_to_official_server(best_solution)

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        conn.close()
        print(f"[DISCONNECTED] {addr} disconnected.")


def main():
    HOST = '0.0.0.0'  # すべてのネットワークインターフェースから接続を待ち受ける
    PORT = 9999       # 任意のポート番号

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[LISTENING] Server is listening on {HOST}:{PORT}")

    while True:
        # クライアントからの接続を待つ
        conn, addr = server.accept()
        # 接続ごとに新しいスレッドを作成して処理
        thread = threading.Thread(target=handle_client, args=(conn, addr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.active_count() - 1}")

if __name__ == "__main__":
    main()
