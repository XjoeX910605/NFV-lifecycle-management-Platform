import os
import subprocess

# 顏色定義
GREEN = '\033[38;5;82m'
YELLOW = '\033[93m'
RED = '\033[91m'
NC = '\033[0m'  # No Color

Operation_dir = "Operation-VNFs"

def modify_ns_info():

    print(f"{YELLOW}\n進行NS相關資訊的修改...\n{NC}")

    # 執行 NS_Info_manager.py
    try:
        result = subprocess.run(
            ["python3","NS_Info_manager.py"],  
            check=True,
            cwd=Operation_dir
        )
        print(f"{YELLOW}修改NS資訊成功\n{NC}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}修改NS資訊失敗\n{e.stderr}{NC}")

def deploy_ns():
    ns_name = input(f"{GREEN}請輸入要部署的NS名稱: {NC}")
    print(f"{YELLOW}部署NS: {ns_name}...{NC}")

    # 執行 Operating_manager.py 進行部署
    try:
        result = subprocess.run(
            ["python3","Operating_Manager.py","deployment", ns_name],  
            check=True,
            cwd=Operation_dir
        )
        print(f"{YELLOW}NS部署成功\n{NC}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}NS部署失敗\n{e.stderr}{NC}")

def scaling_ns():

    # 執行 Operating_manager.py 進行 scaling
    try:
        result = subprocess.run(
            ["python3","Operating_Manager.py","scaling"],  
            check=True,
            cwd=Operation_dir
        )
        print(f"{YELLOW}VNF scaling 執行完畢\n{NC}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}呼叫 Operating Manager 失敗\n{e.stderr}{NC}")
    

def migrate_ns():
    ns_name = input(f"{GREEN}請輸入要進行Migrate的NS名稱: {NC}")
    print(f"{GREEN}執行NS遷移操作...{NC}")
    # 可以根據實際情況進行遷移邏輯的補充
    pass

def main():
    while True:
        print(f"{GREEN}\n選擇您要執行的操作:{NC}")
        print("1. 修改NS相關資訊")
        print("2. 部署NS")
        print("3. Scaling NS")
        print("4. Migrate NS")
        print("5. 退出")
        choice = input(f"{GREEN}請選擇操作: {NC}")
        
        match choice:
            case "1":
                modify_ns_info()
            case "2":
                deploy_ns()
            case "3":
                scaling_ns()
            case "4":
                migrate_ns()
            case "5":
                print(f"{RED}\n退出操作...\n{NC}")
                break
            case _:
                print(f"{RED}\n無效的選擇，請重新選擇{NC}")

if __name__ == "__main__":
    main()
