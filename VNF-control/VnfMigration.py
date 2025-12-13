import json
import subprocess
import time
import sys
import os
import numpy as np
import networkx as nx
from policy_config import MIGRATION_PARAMS

YELLOW = '\033[93m'
GREEN = '\033[38;5;82m'
RED = '\033[91m'
NC = '\033[0m'  # No Color

'''----------------------------------------------參數設定區域----------------------------------------------'''


rounds = MIGRATION_PARAMS["rounds"]    # 輪數
round_length = MIGRATION_PARAMS["round_length"]  # 秒
k_paths = MIGRATION_PARAMS["k_paths"] # 每輪找 k 條路徑
output_round = MIGRATION_PARAMS["output_round"]  # 是否在每輪輸出結果


'''-------------------------------------------------------------------------------------------------------'''

def load_json(filename):  
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current script
    full_path = os.path.join(script_dir, '..', 'Operation-VNFs', filename)
    with open(full_path, 'r') as file:
        data = json.load(file)
    return data

def input_with_default(prompt, default):
    user_input = input(f"{prompt}（例如：{default}）：")
    return user_input.strip() or default


def convert_to_list(data):
    if isinstance(data, list):
        return data  # Already a list
    elif isinstance(data, dict):
        return list(data.values())  # Convert dict values to list
    else:
        return [data]  # Wrap single value in a list

def query_sat_resource(sat_id):
    """用 subprocess 查詢 Operating_Manager.py 資源狀態
    JSON回傳格式範例：
        {
            "hostname": "openstackcompute5",
            "warning": "ID 5 is not in the valid host list, using simulated data.",
            "resource": {
                "total": {
                    "CPU": 4,
                    "Memory_MB": 16384,
                    "Disk_GB": 255
                },
                "used_now": {
                    "CPU": 1,
                    "Memory_MB": 3780,
                    "Disk_GB": 91
                },
                "used_max": {
                    "CPU": 1,
                    "Memory_MB": 12730,
                    "Disk_GB": 197
                }
            }
        }
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current script
    full_path = os.path.join(script_dir, '..', 'Operation-VNFs', 'Operating_Manager.py')
    try:
        result = subprocess.check_output(
            ['python3', full_path, 'resource', str(sat_id)],
            stderr=subprocess.DEVNULL
        )
        res = json.loads(result)
        return res['resource']
    except Exception as e:
        print(f"{RED}  無法查詢衛星 {sat_id} 的資源: {e}{NC}")
        return None



def resource_sufficient(sat_resource_cache,sat_id , vnf):
    """判斷某衛星資源是否能部署某 VNF"""
    available = {
        "cpu": sat_resource_cache[sat_id]['total']['CPU'] - sat_resource_cache[sat_id]['used_now']['CPU'],
        "mem": sat_resource_cache[sat_id]['total']['Memory_MB'] - sat_resource_cache[sat_id]['used_now']['Memory_MB'],
        "disk": sat_resource_cache[sat_id]['total']['Disk_GB'] - sat_resource_cache[sat_id]['used_now']['Disk_GB']
    }
    print(f"    ➤ 檢查衛星 {sat_id} 是否足夠：可用 CPU={available['cpu']}, Mem={available['mem']//1024}GB, Disk={available['disk']}GB")

    return (
        available["cpu"] >= vnf["cpu"] and
        available["mem"] >= vnf["memory"] * 1024 and
        available["disk"] >= vnf["storage"]
    )

def get_migration_endpoints(deploy_path, target_id):
    src = str(deploy_path[target_id - 1]) if target_id > 0 else None
    dst = str(deploy_path[target_id + 1]) if target_id + 1 < len(deploy_path) else None
    return src, dst

def generate_adj_matrix(user_config, seconds_today,output=True):
    """產生鄰接矩陣檔案 adj_matrix.txt 並回傳對應的 graph 物件與 sat_ids"""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(script_dir, '..', 'LEO-satellite-constellation-simulator', 'LEO-satellite-constellation-simulator', 'sattrack')
    input_file_path = os.path.join(directory, 'parameter_example.txt')
    output_file_path = os.path.join(directory, 'parameter.txt')

    # 複製模板內容
    with open(input_file_path, 'r') as input_file:
        content = input_file.read()
    with open(output_file_path, 'w') as output_file:
        output_file.write(content)

    # 加入經緯度與時間參數
    with open(output_file_path, 'a') as file:
        file.write(f">>(outputFileName): (adj_matrix.txt)\n")
        file.write(f">>(execute_function): (printConstellationStateFile)\n")
        file.write(f">>(time):({seconds_today})second")    

    if output:
        print(f"{GREEN}已完成寫入 parameter.txt 參數檔案{NC}")

    # 執行 sattrack
    try:
        if output:
            print(f"{GREEN}執行 ./sattrack 模擬獲取adj matrix中...{NC}")
        with open(os.path.join(directory, 'adj_matrixOutput.txt'), 'w') as output_file:
            subprocess.run(['./sattrack'], cwd=directory, stdout=output_file, stderr=subprocess.STDOUT, check=True)
    except Exception as e:
        print(f"{RED}執行 sattrack 失敗: {e}{NC}")
        return None, None

    adj_output_path = os.path.join(directory, 'adj_matrix.txt')
    if not os.path.exists(adj_output_path):
        print(f"{RED}找不到產出的 adj_matrix.txt{NC}")
        return None, None

    # 讀取並轉換成 graph
    with open(adj_output_path, 'r') as f:
        lines = f.readlines()

    sat_ids = lines[0].strip().split()
    matrix = [list(map(int, line.strip().split()[1:])) for line in lines[1:]]

    G = nx.Graph()
    for i in range(len(sat_ids)):
        for j in range(len(sat_ids)):
            if matrix[i][j] != 0:
                G.add_edge(sat_ids[i], sat_ids[j], weight=1)
    if output:
        print(f"{GREEN}成功生成圖，節點數: {G.number_of_nodes()}，邊數: {G.number_of_edges()}{NC}")
        print(output)
    return G, sat_ids

def get_cover_sats(user_config, seconds_today, output=True):
    """產生 CoverSatsOutput.txt 並回傳對應的 sat_ids 列表"""

    script_dir = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(script_dir, '..', 'LEO-satellite-constellation-simulator', 'LEO-satellite-constellation-simulator', 'sattrack')
    input_file_path = os.path.join(directory, 'parameter_example.txt')
    output_file_path = os.path.join(directory, 'parameter.txt')

    # 複製模板內容
    with open(input_file_path, 'r') as input_file:
        content = input_file.read()
    with open(output_file_path, 'w') as output_file:
        output_file.write(content)

    # 加入經緯度與時間參數
    with open(output_file_path, 'a') as file:
        file.write(f">>(stationLatitude): ({user_config['source_latitude']})\n")
        file.write(f">>(stationLongitude): ({user_config['source_longitude']})\n")
        file.write(f">>(outputFileName): (CoverSats.txt)\n")
        file.write(f">>(execute_function): (printStationCoverSats)\n")
        file.write(f">>(time):({seconds_today})second")    

    if output:
        print(f"{GREEN}已完成寫入 parameter.txt 參數檔案{NC}")

    # 執行 sattrack
    try:
        if output:
            print(f"{GREEN}執行 ./sattrack 模擬獲取覆蓋衛星中...{NC}")
        with open(os.path.join(directory, 'CoverSatsOutput.txt'), 'w') as output_file:
            subprocess.run(['./sattrack'], cwd=directory, stdout=output_file, stderr=subprocess.STDOUT, check=True)
    except Exception as e:
        print(f"{RED}執行 sattrack 失敗: {e}{NC}")
        return None, None

    output_path = os.path.join(directory, 'CoverSats.txt')
    if not os.path.exists(output_path):
        print(f"{RED}找不到產出的 CoverSats.txt{NC}")
        return None, None
    
    with open(output_path, 'r') as f:
        lines = f.readlines()
    sats = set()
    for line in lines:
        if ':' in line:
            sats_str = line.strip().split(':')[1]
            for sid in sats_str.strip().split(','):
                if sid.strip().isdigit():
                    sats.add(sid.strip())
    return list(sats)

def migration_with_rounds(user_config, deploy_path, target_vnf, round_num, round_len_sec, k_paths=3, output=True):
    """
    模擬多輪 VNF 遷移決策過程。
    每輪根據當時的衛星拓樸重建圖，並重新計算該 VNF 的最短路徑。
    若起點或終點為 NS 的端點，則以 get_cover_sats() 擴展成多個候選衛星。
    最後取所有輪中皆出現的衛星作為穩定可用節點。
    """

    from datetime import datetime, timedelta
    from networkx.algorithms.simple_paths import shortest_simple_paths

    base_time = datetime.now()
    target_id = target_vnf["id"]
    all_paths = []

    for r in range(round_num):
        # === 每輪時間點 ===
        now = base_time + timedelta(seconds=r * round_len_sec)
        seconds_today = now.hour * 3600 + now.minute * 60 + now.second
        if output:
            print(f"\n{YELLOW}>>> Round {r+1}, Time = {seconds_today} sec{NC}")

        # === 每輪重新取得衛星圖 ===
        G, _ = generate_adj_matrix(user_config, seconds_today, output)

        # === 找出前後相鄰衛星 ===
        src, dst = get_migration_endpoints(deploy_path, target_id)

        if output:
            print(f"{YELLOW}⚙ VNF {target_vnf['vnf_name']} 的遷移起點: {src}，終點: {dst}{NC}")
        # === 初始化起點與終點清單 ===
        src_list = [src]
        dst_list = [dst]

        # === 若起點是 NS 的起點，取當下能服務起點的 cover sats ===
        if target_id-1 == 0:
            src_list = get_cover_sats(user_config, seconds_today, output)
            if output:
                print(f"{YELLOW}⚙ 起點為 NS 起點，擴展為 cover sats：{src_list}{NC}")

        # === 若終點是 NS 的終點，取當下能服務終點的 cover sats ===
        if target_id+1 == len(deploy_path) - 1:
            dst_list = get_cover_sats(user_config, seconds_today, output)
            if output:
                print(f"{YELLOW}⚙ 終點為 NS 終點，擴展為 cover sats：{dst_list}{NC}")

        # === 搜尋所有起點與終點組合的最短路徑 ===
        round_paths = []
        for s in src_list:
            for d in dst_list:
                if nx.has_path(G, s, d):
                    paths = shortest_simple_paths(G, source=s, target=d)
                    for counter, path in enumerate(paths):
                        if output:
                            print(f"{GREEN}✓ 路徑 {s} -> {d}：{path}{NC}")
                        round_paths.append(path)
                        if counter + 1 == k_paths:
                            break
                else:
                    if output:
                        print(f"{RED}✘ 無法從 {s} 到 {d} 找到通訊路徑{NC}")

        all_paths.append(round_paths)

    # === 共通節點交集（找出所有輪皆穩定存在的衛星） ===
    if not all_paths or not all_paths[0]:
        print(f"{RED}✘ 無任何路徑可用，請確認起訖衛星有連通{NC}")
        return

    # 初始化為第一輪所有候選路徑的 union
    final_nodes = set()
    for p in all_paths[0]:
        final_nodes.update(p)

    # 逐輪縮小
    for round_group in all_paths[1:]:
        merged = set()
        for path in round_group:
            merged.update(path)
        final_nodes.intersection_update(merged)

    print(f"\n{GREEN}✓ 所有輪皆存在的共同節點（可穩定使用的衛星）：{sorted(final_nodes)}{NC}")

    # 在所有穩定節點中評估資源足夠與否
    print(f"\n{YELLOW}▶ 對穩定節點進行資源評估...{NC}")

    candidate_scores = []

    for sid in final_nodes:
        res = query_sat_resource(sid)
        if res is None:
            continue

        total = res["total"]
        used = res["used_now"]

        # 檢查資源是否足夠
        enough = (
            (total["CPU"] - used["CPU"] >= target_vnf["cpu"]) and
            (total["Memory_MB"] - used["Memory_MB"] >= target_vnf["memory"] * 1024) and
            (total["Disk_GB"] - used["Disk_GB"] >= target_vnf["storage"])
        )

        if not enough:
            print(f"{RED}✘ 衛星 {sid} 資源不足，排除{NC}")
            continue

        # 計算三項使用率
        cpu_ratio  = (used["CPU"] + target_vnf["cpu"]) / total["CPU"]
        mem_ratio  = (used["Memory_MB"] + target_vnf["memory"] * 1024) / total["Memory_MB"]
        disk_ratio = (used["Disk_GB"] + target_vnf["storage"]) / total["Disk_GB"]

        # 檢查是否超過使用率上限
        limit = MIGRATION_PARAMS["limit"]
        weights = MIGRATION_PARAMS["weights"]

        if cpu_ratio > limit["cpu"] or mem_ratio > limit["mem"] or disk_ratio > limit["disk"]:
            print(f"{RED}✘ 衛星 {sid} 使用率將超標，排除{NC}")
            continue

        # 計算 score
        score = (
            cpu_ratio * weights["cpu"] +
            mem_ratio * weights["mem"] +
            disk_ratio * weights["disk"]
        )

        candidate_scores.append((sid, score, cpu_ratio, mem_ratio, disk_ratio))

        print(f"{GREEN}✓ 衛星 {sid} 可用，Score={score:.4f}{NC}")

    if not candidate_scores:
        print(f"{RED}✘ 無衛星同時滿足：穩定 + 資源足夠 + 不超限{NC}")
        return

    # 依 score 選最終遷移節點
    best_sid, best_score, cr, mr, dr = min(candidate_scores, key=lambda x: x[1])

    print(f"\n{GREEN}=== 最終遷移目標節點 ===")
    print(f"衛星 {best_sid}（Score={best_score:.4f}）")
    print(f"CPU={cr*100:.1f}%  MEM={mr*100:.1f}%  Disk={dr*100:.1f}%{NC}")




def main():

    print(f"{GREEN}正在執行 VNF Migration 決策模組{NC}\n\n")
    if len(sys.argv) < 3:
        print(f"{RED}請輸入要部署之 NS 名稱 以及 VNF 名稱，例如 python3 VnfMigration.py test vnf1{NC}")
        return

    ns_name = sys.argv[1]
    target_vnf_name = sys.argv[2]

    config = load_json('ns_vnf_config.json')
    user_config = config[ns_name]

    print(f"{GREEN}目標 NS: {ns_name}，目標 VNF: {target_vnf_name}{NC}")
    print(f"{GREEN}載入 NS 配置成功，開始進行 VNF 遷移決策模組運算...{NC}\n")
    print(f"{GREEN}NS 配置內容如下：{NC}")
    print(user_config)
    print(f"{YELLOW}\n參數設定如下：")
    print(f"  rounds = {rounds}")
    print(f"  round_length = {round_length} 秒")
    print(f"  k_paths = {k_paths} 條路徑")
    print(f"  output_round = {output_round}\n{NC}")

    deploy_path = user_config.get("path", [])
    target_vnf = None
    for vnf in user_config["vnfs"]:
        if vnf["vnf_name"] == target_vnf_name:      
            target_vnf = vnf
            break

   

    migration_with_rounds(user_config, deploy_path, target_vnf, rounds, round_length, k_paths, output_round)

    # -------------------------------------------------------------- 測試用 -------------------------------------------------------------- #

    # rounds = int(input_with_default("請輸入要模擬幾輪（round 數）: ", 2))
    # round_length = int(input_with_default("請輸入每輪的時間間隔（秒）: ", 30))

    # # 取得當前時間（秒）
    # from datetime import datetime

    # now = datetime.now()
    # seconds_today = now.hour * 3600 + now.minute * 60 + now.second
    # seconds_today = input_with_default("請輸入秒數: ", seconds_today)
    # print(f"今天已經過了 {seconds_today} 秒")

    # G, sat_ids = generate_adj_matrix(user_config, seconds_today)
    # if G is None:
    #     print(f"{RED}產生 adj_matrix 發生錯誤，中止後續流程{NC}")
    #     return

    
    # # 印出圖中節點數與邊數
    # print("節點數:", G.number_of_nodes())
    # print("邊數:", G.number_of_edges())
    # print("圖中共有節點數：", len(G.nodes))
    # print("節點清單：", list(G.nodes))


    # print(target_vnf)
    # source_sat = str(deploy_path[target_vnf["id"] - 1])
    # target_sat = str(deploy_path[target_vnf["id"] + 1])
    # print(f"將以衛星 {source_sat} → {target_sat} 作為 VNF {target_vnf_name} 的路徑查找")

    # # 使用 networkx 查最短路徑
    # if nx.has_path(G, source_sat, target_sat):
    #     shortest_path = nx.shortest_path(G, source=source_sat, target=target_sat)
    #     print(f"✓ 最短路徑為: {shortest_path}")
    # else:
    #     print(f"✘ 無法從 {source_sat} 到 {target_sat} 找到通訊路徑")
    
    # get_cover_sats(user_config, seconds_today)
    

if __name__ == "__main__":
    main()
