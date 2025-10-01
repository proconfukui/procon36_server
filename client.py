import socket
import json
import time
import random
from typing import Dict, Any

# サーバーPCのIPアドレスとポート
# TODO: 正式なものに書き換える
SERVER_HOST: str = "192.168.11.32"  # サーバーの実際のIPアドレス
SERVER_PORT: int = 8888

def run_solver(match_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    計算アルゴリズムを実行して解を生成するダミー関数。
    TODO: この関数を、実際の計算プログラムを呼び出して
          その標準出力を受け取る処理に置き換える。
    """
    print("ソルバーを実行中...")

    # 計算に時間がかかったと仮定
    time.sleep(5)
    
    # ダミーの解を生成 (ペア数と回転数はランダム)
    num_pairs: int = random.randint(5, 10)
    num_rotations: int = random.randint(50, 100)

    solution: Dict[str, Any] = {
        "pair_count": num_pairs, # 解の比較用。サーバー側で取り除かれる
        "ops": [
            {"x": x, "y": y, "n": n}
            for x, y, n in zip([0] * num_rotations, [0] * num_rotations, [2] * num_rotations)
        ]
    }
    print(f"ソルバー実行完了（ペア数：{num_pairs}、手数：{num_rotations}）")
    return solution

def main() -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # サーバーに接続
            print(f"{SERVER_HOST}:{SERVER_PORT}に接続中...")
            s.connect((SERVER_HOST, SERVER_PORT))
            print("接続成功。問題受信を待機...")
            
            # サーバーから問題を受け取る
            data: bytes = b""
            while True:
                chunk: bytes = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            if not data:
                print("エラー：サーバーから受信ができませんでした")
                return
            match_info: Dict[str, Any] = json.loads(data.decode("utf-8"))
            print("問題受信に成功")

            # ソルバーを実行
            solution: Dict[str, Any] = run_solver(match_info)
            
            # 解をサーバーに送信
            print("解をサーバーに送信中...")
            s.sendall(json.dumps(solution).encode("utf-8"))
            print("解をサーバーに送信完了")
    except Exception as e:
        print(f"エラー：{e}")

if __name__ == "__main__":
    main()
