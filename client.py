import socket
import json
import time
import random

# ★★★ サーバーPCのIPアドレスをここに入力 ★★★
SERVER_HOST = '192.168.1.10' # 例: サーバー役のPCのIPアドレス
SERVER_PORT = 9999

def run_solver():
    """
    計算アルゴリズムを実行して解を生成するダミー関数。
    TODO: この関数を、実際の計算プログラムを呼び出して
          その標準出力を受け取る処理に置き換える。
    """
    print("Running solver...")
    # ダミーの解を生成 (ペア数と回転数はランダム)
    num_pairs = random.randint(5, 10)
    num_rotations = random.randint(50, 100)

    solution = {
        "pair_count": num_pairs, # 解の比較用。サーバー側で取り除かれる
        "ops": [
            {"x": x, "y": y, "n": n}
            for x, y, n in zip(
                random.choices(range(10), k=num_rotations),
                random.choices(range(10), k=num_rotations),
                random.choices(range(10), k=num_rotations)
            )
        ]
    }
    print(f"Solver finished. Found a solution with {num_pairs} pairs and {num_rotations} rotations.")
    return solution

def send_solution_to_server(solution):
    """サーバーに解を送信する"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            print(f"Connecting to server {SERVER_HOST}:{SERVER_PORT}...")
            s.connect((SERVER_HOST, SERVER_PORT))
            
            # 辞書をJSON形式の文字列に変換し、バイトデータにエンコードして送信
            s.sendall(json.dumps(solution).encode('utf-8'))
            print("Solution sent successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to send solution: {e}")


def main():
    # 30秒ごとに新しい解を見つけたと仮定してサーバーに送り続けるループ
    while True:
        solution = run_solver()
        send_solution_to_server(solution)
        time.sleep(30) # 30秒待機

if __name__ == "__main__":
    main()
