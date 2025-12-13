import sys
import subprocess
import json
import os
import random


CONFIG_FILE = "ns_vnf_config.json"
remote_user="stack"
remote_ip="192.168.100.148"


YELLOW = '\033[93m'
GREEN = '\033[38;5;82m'
RED = '\033[91m'
NC = '\033[0m'  # No Color

def load_config():
    """
    載入 ns_vnf_config.json 配置檔，返回 Python dict。
    若檔案不存在，回傳空 dict。
    """
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def build_osm_pkg_targz(pkgfolder):
    """
    將指定的 pkgfolder（放在 OSM_pkg/ 下）打包成 .tar.gz 格式，
    以便後續上傳至 OSM。
    """
    full_path = os.path.join("OSM_pkg", pkgfolder)
    try:
        if not os.path.isdir(full_path):
            print(f"{RED}資料夾不存在：{full_path}{NC}")
            return
        result = subprocess.run(
            ["osm", "package-build", full_path],
            check=True,
            capture_output=True,
            text=True
        )
        print(f"{GREEN}打包成功：\n{result.stdout}{NC}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}打包失敗：\n{e.stderr}{NC}")

def upload_osm_pkg_targz(pkgfolder):
    """
    上傳已經打包好的 .tar.gz 檔案至 OSM：
    - 如果 pkgfolder 含 "_ns"，則使用 nspkg-create
    - 如果 pkgfolder 含 "_vnf"，則使用 nfpkg-create
    """
    full_path = os.path.join("OSM_pkg", pkgfolder + ".tar.gz")
    try:
        if "_ns" in pkgfolder:
            command = ["osm", "nspkg-create", full_path]
        elif "_vnf" in pkgfolder:
            command = ["osm", "nfpkg-create", full_path]
        else:
            print(f"{RED}無法辨識的套件類型：{pkgfolder}{NC}")
            return

        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"{GREEN}上傳成功：\n{result.stdout}{NC}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}上傳失敗：\n{e.stderr}{NC}")

def deploy(ns_name):
    """
    部署網路服務：
    1. 呼叫 Generate_OSM_pkg.py 產生 NS 與 VNF 的 descriptor
    2. 根據配置檔打包並上傳所有 VNF package
    3. 打包並上傳 NS package
    4. 執行 osm ns-create 建立 NS instance
    """
    print(f"{GREEN}[部署中] 執行 Network Service 部署：{ns_name}{NC}")

    # 1. 透過外部腳本自動產生 OSM descriptor（Generate_OSM_pkg.py）
    try:
        subprocess.run(["python3", "Generate_OSM_pkg.py", ns_name], check=True)
    except subprocess.CalledProcessError as e:
        print(f"{RED}產生 OSM pkg 失敗：{e}{NC}")
        return

    # 2. 讀取配置檔，確定 NS 與 VNF 相關資訊
    config = load_config()
    ns_info = config.get(ns_name)
    if not ns_info:
        print(f"{RED}找不到 NS 名稱：{ns_name}{NC}")
        return

    # 3. 依序打包並上傳每個 VNF package
    for vnf in ns_info.get("vnfs", []):
        vnf_name = vnf.get("vnf_name")
        if vnf_name:
            vnf_pkg_folder = f"{vnf_name}_vnf"
            print(f"{GREEN}\n正在打包 VNF 套件：{vnf_pkg_folder}{NC}")
            build_osm_pkg_targz(vnf_pkg_folder)

            print(f"{GREEN}正在上傳 VNF 套件：{vnf_pkg_folder}{NC}")
            upload_osm_pkg_targz(vnf_pkg_folder)
        else:
            print(f"{RED}VNF 缺少名稱，略過。{NC}")

    # 4. 打包並上傳 NS package
    ns_pkg_folder = f"{ns_name}_ns"
    print(f"{GREEN}正在打包 NS 套件：{ns_pkg_folder}{NC}")
    build_osm_pkg_targz(ns_pkg_folder)

    print(f"{GREEN}正在上傳 NS 套件：{ns_pkg_folder}{NC}")
    upload_osm_pkg_targz(ns_pkg_folder)

    # 5. 部署 NS instance
    try:
        subprocess.run(
            ["osm", "ns-create",
             "--ns_name", ns_name,
             "--nsd_name", ns_name,
             "--vim_account", "openstack-multinode",
             "--wait"],
            check=True
        )
        print(f"{GREEN}[完成]{NC} NS {ns_name} 部署成功。")
    except subprocess.CalledProcessError as e:
        print(f"{RED}部署 NS 失敗：\n{e.stderr}{NC}")
        return

# --------- 以下為 Scaling 所需的輔助函式 ----------

def run_command(cmd):
    """
    執行一個 shell 指令，回傳 stdout (strip 後)。
    若指令執行失敗，則印出錯誤訊息並結束程式。
    """
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"{GREEN}[錯誤]{NC} 無法執行指令：{' '.join(cmd)}")
        print(e.stderr)
        sys.exit(1)

def list_ns_instances():
    """
    使用 `osm ns-list` 列出所有正在執行的 NS-instance，解析出 ns_name 與 status。
    回傳格式：[{ "ns_name": "...", "status": "..." }, ...]
    """
    output = run_command(["osm", "ns-list"])
    lines = [l for l in output.splitlines() if l.strip().startswith("|") and "NAME" not in l]
    instances = []
    for line in lines:
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 3:
            instances.append({
                "ns_name": parts[0],
                "status": parts[2]
            })
    return instances

def list_vnfs_of_ns(ns_name):
    """
    使用 `osm vnf-list --ns <ns_name>` 列出該 NS-instance 底下所有 VNF，
    並解析出「vnf member index」、VNF 名稱、VNFD 名稱、VNF ID 等欄位。
    回傳格式：
      [
        {
          "vnf_id": "...",
          "vnf_name": "...",
          "vnfd_name": "...",
          "member_index": "1"
        },
        ...
      ]
    """
    # 1. 執行 osm vnf-list --ns <ns_name>
    output = run_command(["osm", "vnf-list", "--ns", ns_name])
    lines = [l for l in output.splitlines() if l.strip().startswith("|")]

    header_idx = None    # 用來記錄「vnf member index」欄位所在的索引
    headers = []
    vnfs = []

    # 2. 找出標頭列，定位「包含 'index'（不分大小寫）」的那個欄位索引
    for line in lines:
        parts = [p.strip() for p in line.strip("|").split("|")]
        # 當列中有任意一個欄位文字包含 "index"（忽略大小寫）時，視為標頭
        if any("index" in p.lower() for p in parts):
            headers = parts
            for i, h in enumerate(headers):
                if "index" in h.lower():
                    header_idx = i
                    break
            break

    if header_idx is None:
        print(f"{GREEN}[錯誤]{NC} 在 `osm vnf-list --ns {ns_name}` 的輸出中找不到「index」欄位！")
        sys.exit(1)

    # 3. 解析每一筆資料列（排除標頭列本身），取得對應欄位
    for line in lines:
        parts = [p.strip() for p in line.strip("|").split("|")]
        # 若這一列剛好等於 headers（也就是標頭本身），跳過
        if parts == headers:
            continue
        # 若欄位數量不包含 member_index，跳過
        if len(parts) <= header_idx:
            continue

        # 解析常見欄位：
        vnf_id       = parts[0]                  # 第一欄：vnf id
        vnf_name     = parts[1]                  # 第二欄：name
        # parts[2] 是 ns id，可視需求保留或忽略
        vnfd_name    = parts[4] if len(parts) > 4 else ""  # 第五欄：vnfd name
        member_index = parts[header_idx]         # 找到的「vnf member index」欄位

        vnfs.append({
            "vnf_id": vnf_id,
            "vnf_name": vnf_name,
            "vnfd_name": vnfd_name,
            "member_index": member_index
        })

    return vnfs


def prompt_select(prompt_message, options):
    """
    顯示互動式選單，列出 options 列表（字串），讓使用者輸入索引以選擇。
    回傳使用者選中的索引（int）。
    """
    if not options:
        print(f"{GREEN}[提示] 沒有可選的項目！{NC}")
        sys.exit(1)

    print(prompt_message)
    for idx, opt in enumerate(options):
        print(f"  {GREEN}[{idx}]{NC} {opt}")

    while True:
        choice = input("請輸入編號：").strip()
        if choice.isdigit() and 0 <= int(choice) < len(options):
            return int(choice)
        print("輸入不合法，請再次輸入序號。")

def scale():
    print(f"{GREEN}[scaling...]開始執行 VNF 擴展或縮減...{NC} ")

    # 1. 列出所有 NS-instance
    ns_list = list_ns_instances()
    ns_names = [f"{item['ns_name']} (狀態: {item['status']})" for item in ns_list]
    selected_ns_idx = prompt_select("請選擇要操作的 NS-instance：", ns_names)
    ns_name = ns_list[selected_ns_idx]["ns_name"]

    # 2. 列出該 NS-instance 底下所有 VNF（包含 member_index）
    print(f"{GREEN}[查詢]{NC} 取得 NS={ns_name} 底下的 VNF 列表...")
    vnfs = list_vnfs_of_ns(ns_name)
    if not vnfs:
        print(f"{GREEN}[提示]{NC} NS-instance {ns_name} 下沒有可用的 VNF！")
        sys.exit(1)

    # 3. 建立選單，顯示：VNF 名稱
    vnf_opts = [
        f"{v['vnfd_name']}"
        for v in vnfs
    ]
    selected_vnf_idx = prompt_select("請選擇要 scale 的 VNF：", vnf_opts)

    # 4. 改為從 vnfs[selected_vnf_idx]["member_index"] 取得索引
    vnf_index = vnfs[selected_vnf_idx]["member_index"]

    # 5. 讓使用者選擇 scale-out 或 scale-in
    print("請選擇擴縮操作：")
    print(f"  {GREEN}[0]{NC} scale-out")
    print(f"  {GREEN}[1]{NC} scale-in")
    while True:
        op = input("輸入 0 或 1：").strip()
        if op in ["0", "1"]:
            op = int(op)
            break
        print("輸入不合法，請重新輸入。")

    # 6. scaling-group 名稱（若留空則用預設）
    scaling_group = input("請輸入 scaling group 名稱（預設 manual-scaling_mgmtVM）：").strip()
    if not scaling_group:
        scaling_group = "manual-scaling_mgmtVM"

    # 7. 組成 osm vnf-scale 指令並執行
    if op == 0:
        cmd = [
            "osm", "vnf-scale",
            "--scale-out", ns_name, vnf_index,
            "--scaling-group", scaling_group,
            "--wait"
        ]
        action = "scale-out"
    else:
        cmd = [
            "osm", "vnf-scale",
            "--scale-in", ns_name, vnf_index,
            "--scaling-group", scaling_group,
            "--wait"
        ]
        action = "scale-in"
    print(f"{GREEN}[執行]{NC} 正在對 NS={ns_name} 、VNF={vnfs[selected_vnf_idx]['vnfd_name']} 進行 {action} ...")
    confirm = input(f"確定要對 {ns_name} 的 {vnfs[selected_vnf_idx]['vnfd_name']} 做 {action} 嗎？(y/n)：").strip().lower()
    if confirm != 'y':
        print("使用者取消操作。")
        return

    try:
        subprocess.run(cmd, check=True)
        print(f"{GREEN}[完成]{NC} {action} 操作已執行完畢。")
    except subprocess.CalledProcessError as e:
        print(f"{RED}[錯誤]{NC} 無法完成 {action} 操作！\n{e.stderr}")

def migrate(ns_name, vnf_name, sat_id):
    print(f"{GREEN}[遷移中] 將 {vnf_name} 從 NS {ns_name} 遷移至衛星 {sat_id}...{NC}")
    
    # Step 1: 透過 ssh 執行 openstack server list
    cmd_list = (
        f'ssh {remote_user}@{remote_ip} '
        f'". ~/devstack/openrc admin demo && openstack server list -f json"'
    )
    try:
        list_result = subprocess.run(cmd_list, shell=True, capture_output=True, text=True, check=True)
        vm_list = json.loads(list_result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"{RED}[錯誤]{NC} 查詢 VM 清單失敗：{e.stderr}")
        return

    vm_name = None
    for vm in vm_list:
        name = vm.get("Name", "")
        if ns_name in name and vnf_name in name:
            vm_name = name
            break

    if not vm_name:
        print(f"{RED}[錯誤]{NC} 找不到對應 VM 名稱。")
        return

    print(f"{GREEN}[發現] VM 名稱：{vm_name}{NC}")

    hostname = f"openstackcompute{sat_id}"
    print(f"{GREEN}[目標] 遷移至主機：{hostname}{NC}")

    # Step 3: 遠端執行遷移指令
    cmd_migrate = (
        f'ssh {remote_user}@{remote_ip} '
        f'". ~/devstack/openrc admin demo && openstack server migrate {vm_name} --host {hostname}  --wait"'
    )
    try:
        subprocess.run(cmd_migrate, shell=True, check=True)
        print(f"{GREEN}[成功]{NC} 遷移完成！")
    except subprocess.CalledProcessError as e:
        print(f"{RED}[錯誤]{NC} 遷移失敗：{e.stderr}")



def resource(sat_id):
    current_hosts = [1, 2]

    def generate_consistent_resource():
        total_cpu = random.choice([4, 8, 16, 32])
        total_mem = total_cpu * random.choice([2048, 4096])
        total_disk = random.randint(100, 500)

        used_now_cpu = random.randint(0, total_cpu)
        used_now_mem = random.randint(0, total_mem)
        used_now_disk = random.randint(0, total_disk)

        used_max_cpu = max(used_now_cpu, random.randint(used_now_cpu, total_cpu))
        used_max_mem = max(used_now_mem, random.randint(used_now_mem, total_mem))
        used_max_disk = max(used_now_disk, random.randint(used_now_disk, total_disk))

        return {
            "total": {"CPU": total_cpu, "Memory_MB": total_mem, "Disk_GB": total_disk},
            "used_now": {"CPU": used_now_cpu, "Memory_MB": used_now_mem, "Disk_GB": used_now_disk},
            "used_max": {"CPU": used_max_cpu, "Memory_MB": used_max_mem, "Disk_GB": used_max_disk},
        }

    if int(sat_id) not in current_hosts:
        fake = generate_consistent_resource()
        hostname = f"openstackcompute{sat_id}"
        return {
            "hostname": hostname,
            "warning": f"ID {sat_id} is not in the valid host list, using simulated data.",
            "resource": fake
        }

    hostname = f"openstackcompute{sat_id}"

    remote_cmd = (
        f"ssh {remote_user}@{remote_ip} "
        f"\". ~/devstack/openrc admin demo && openstack host show {hostname} -f json\""
    )

    try:
        result = subprocess.run(remote_cmd, shell=True, check=True, text=True, capture_output=True)
        json_output = result.stdout
        data = json.loads(json_output)

        def extract_info(label):
            for entry in data:
                if entry["Project"] == label:
                    return {
                        "CPU": int(entry["CPU"]),
                        "Memory_MB": int(entry["Memory MB"]),
                        "Disk_GB": int(entry["Disk GB"])
                    }
            return {"CPU": 0, "Memory_MB": 0, "Disk_GB": 0}

        total = extract_info("(total)")
        used_now = extract_info("(used_now)")
        used_max = extract_info("(used_max)")

        return {
            "hostname": hostname,
            "resource": {
                "total": total,
                "used_now": used_now,
                "used_max": used_max
            }
        }

    except subprocess.CalledProcessError as e:
        return {
            "hostname": hostname,
            "error": f"Failed to query host resources: {e.stderr}"
        }
    except json.JSONDecodeError:
        return {
            "hostname": hostname,
            "error": "JSON parsing failed, possibly due to format error or incorrect execution of the openstack command."
        }





def main():
    if len(sys.argv) < 2:
        print(f"{RED}請輸入操作參數：deployment / scaling / migration{NC}")
        return
    operation = sys.argv[1].lower()
    match operation:
        case "deployment":
            if len(sys.argv) < 3:
                print(f"{RED}請輸入要部署的 NS 名稱，例如：FL{NC}")
                return
            ns_name = sys.argv[2]
            deploy(ns_name)
        case "scaling":
            scale()
        case "migration":
            if len(sys.argv) < 5:
                print(f"{RED}請輸入 NS 名稱、VNF 名稱及衛星 ID，例如：migration FL FL_client 1{NC}")
                return
            ns_name = sys.argv[2]
            vnf_name = sys.argv[3]
            sat_id = sys.argv[4]
            migrate(ns_name, vnf_name, sat_id)
        case "resource":
            if len(sys.argv) < 3:
                print(f"{RED}請輸入要查詢的衛星id{NC}")
                return
            sat_id = sys.argv[2]
            info = resource(sat_id)
            print(json.dumps(info, indent=4))
        case _:
            print(f"{RED}不支援的操作，請輸入：deployment / scaling / migration{NC}")

if __name__ == "__main__":
    main()
