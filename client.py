import socket
import json
import os
import subprocess
from typing import Dict, Any

# サーバーPCのIPアドレスとポート
# TODO: 正式なものに書き換える
SERVER_HOST: str = "192.168.11.32"  # サーバーの実際のIPアドレス
SERVER_PORT: int = 8888

# ソルバーで必要なファイルのパス
PROBLEM_PATH: str = "testcase/problem.json"
ANSWER_PATH: str = "testcase/answer.json"
WEIGHT_PATH: str = "testcase/weights.txt"
WEIGHT_START_LINE: int = 1 # 使用する重みの行番号（1始まり）
INPUT_PROBLEM_PATH: str = "./bin/input_problem.exe"
MAIN_SHELL_PATH: str = "./main.sh"
MAIN_CPP_PATH: str = "./bin/main.exe"
CREATE_ANSWER_JSON_PATH: str = "./bin/create_answer_json.exe"

# ソルバーを実行して解を生成する
def run_solver(match_info: Dict[str, Any]) -> Dict[str, Any]:
    print("ソルバーを実行中...")

    # testcaseディレクトリがなければ作成
    os.makedirs("testcase", exist_ok=True)

    try:
        with open(PROBLEM_PATH, 'w') as f:
            json.dump(match_info, f, indent=4)
        print(f"{PROBLEM_PATH} に試合情報を書き込み成功")

        # 一連のコマンドを実行
        command = f"{MAIN_SHELL_PATH} {PROBLEM_PATH} {WEIGHT_PATH} {WEIGHT_START_LINE} {MAIN_CPP_PATH} | {CREATE_ANSWER_JSON_PATH} {ANSWER_PATH}"
        print(f"コマンドを実行：{command}")
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print("コマンドの実行完了")

        # 標準出力や標準エラー出力を表示 (デバッグ用)
        if result.stdout:
            print("ソルバーの標準出力：", result.stdout)
        if result.stderr:
            print("ソルバーのエラー出力：", result.stderr)

        # 結果ファイルを読み込む
        print(f"{ANSWER_PATH} から解を読み込み...")
        with open(ANSWER_PATH, 'r') as f:
            solution = json.load(f)
        
        print(f"読み込み成功。ソルバー実行完了")
        return solution

    except FileNotFoundError:
        print(f"エラー：ソルバーの実行ファイルが見つかりません")
        return {}
    except subprocess.CalledProcessError as e:
        print(f"エラー：コマンドが終了コード{e.returncode}で失敗")
        print("ソルバーのエラー出力：", e.stderr)
        return {}
    except Exception as e:
        print(f"エラー：{e}")
        return {}

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
                chunk: bytes = s.recv(8192)
                if not chunk:
                    break
                data += chunk
            if not data:
                print("エラー：サーバーから受信ができませんでした")
                return
            match_info: Dict[str, Any] = json.loads(data.decode("utf-8"))
            print("問題受信に成功")

            while True:
                # ソルバーを実行
                solution: Dict[str, Any] = run_solver(match_info)

                # 解をサーバーに送信
                if solution:
                    print("解をサーバーに送信中...")
                    # ソケットが閉じられている可能性があるので、新しい接続を作成する
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sender_socket:
                        sender_socket.connect((SERVER_HOST, SERVER_PORT))
                        sender_socket.sendall(json.dumps(solution).encode('utf-8'))
                    print("解をサーバーに送信完了")
                else:
                    print("解が生成されませんでした。再試行します。")
    except Exception as e:
        print(f"エラー：{e}")

if __name__ == "__main__":
    main()
