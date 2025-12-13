import json
import subprocess
import time
import sys
import os
import copy
from policy_config import PLACEMENT_PARAMS

YELLOW = '\033[93m'
GREEN = '\033[38;5;82m'
RED = '\033[91m'
NC = '\033[0m'  # No Color

weights = PLACEMENT_PARAMS["weights"]   # ← 讀取使用者設定的權重
limit = PLACEMENT_PARAMS["limit"]



def load_json(filename):  
    script_dir = os.path.dirname(os.path.abspath(__file__))  # Get the directory of the current script
    full_path = os.path.join(script_dir, '..', 'Operation-VNFs', filename)
    with open(full_path, 'r') as file:
        data = json.load(file)
    return data


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
        # used = res['resource']['used_now']
        # total = res['resource']['total']
        # print(f"{GREEN}  查詢衛星 {sat_id} ......{NC}")
        # return {
        #     "cpu": total["CPU"] - used["CPU"],
        #     "mem": total["Memory_MB"] - used["Memory_MB"],
        #     "disk": total["Disk_GB"] - used["Disk_GB"]
        # }
    except Exception as e:
        print(f"{RED}  無法查詢衛星 {sat_id} 的資源: {e}{NC}")
        return None


def resource_sufficient(sat_resource_cache, sat_id, vnf):
    """判斷某衛星資源是否能部署某 VNF，並檢查是否超過使用率上限"""

    available = {
        "cpu": sat_resource_cache[sat_id]['total']['CPU'] - sat_resource_cache[sat_id]['used_now']['CPU'],
        "mem": sat_resource_cache[sat_id]['total']['Memory_MB'] - sat_resource_cache[sat_id]['used_now']['Memory_MB'],
        "disk": sat_resource_cache[sat_id]['total']['Disk_GB'] - sat_resource_cache[sat_id]['used_now']['Disk_GB']
    }

    print(f"    ➤ 檢查衛星 {sat_id}：可用 CPU={available['cpu']}, Mem={available['mem']//1024}GB, Disk={available['disk']}GB")

    # 基本資源夠不夠
    if not (
        available["cpu"] >= vnf["cpu"] and
        available["mem"] >= vnf["memory"] * 1024 and
        available["disk"] >= vnf["storage"]
    ):
        return False


    # 檢查使用率是否超過限制

    total = sat_resource_cache[sat_id]['total']

    # 部署後的預估使用率
    cpu_ratio = (sat_resource_cache[sat_id]['used_now']['CPU'] + vnf["cpu"]) / total['CPU']
    mem_ratio = (sat_resource_cache[sat_id]['used_now']['Memory_MB'] + vnf["memory"] * 1024) / total['Memory_MB']
    disk_ratio = (sat_resource_cache[sat_id]['used_now']['Disk_GB'] + vnf["storage"]) / total['Disk_GB']

    if cpu_ratio > limit["cpu"]:
        print(f"{RED}    ⚠ CPU 使用率將達 {cpu_ratio*100:.1f}% 超過上限{limit['cpu']*100}%{NC}")
        return False
    if mem_ratio > limit["mem"]:
        print(f"{RED}    ⚠ Mem 使用率將達 {mem_ratio*100:.1f}% 超過上限{limit['mem']*100}%{NC}")
        return False
    if disk_ratio > limit["disk"]:
        print(f"{RED}    ⚠ Disk 使用率將達 {disk_ratio*100:.1f}% 超過上限{limit['disk']*100}%{NC}")
        return False

    return True


def main():

    print(f"{GREEN}正在執行 VNF Placement 決策模組{NC}\n\n")
    if len(sys.argv) < 2:
        print(f"{RED}請輸入要部署之 NS 名稱{NC}")
        return

    ns_name = sys.argv[1]

    # Set the directory to execute the command
    script_dir = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(script_dir, '..', 'LEO-satellite-constellation-simulator', 'LEO-satellite-constellation-simulator', 'sattrack')
    # If you want to use a relative path, you can uncomment the line below
    # directory = '../LEO-satellite-constellation-simulator/LEO-satellite-constellation-simulator/sattrack/'
    


    config = load_json('ns_vnf_config.json')
    user_config = config[ns_name]
    print(user_config)
    
    # Specify the file paths
    input_file_path = os.path.join(directory , 'parameter_example.txt')
    output_file_path = os.path.join(directory, 'parameter.txt')


    # Read from parameter_example.txt and write to parameter.txt
    try:
        with open(input_file_path, 'r') as input_file:
            content = input_file.read()  # Read the content of the input file
        
        with open(output_file_path, 'w') as output_file:
            output_file.write(content)  # Write the content to the output file

        print(f"\nContent from {input_file_path} has been written to {output_file_path}.\n")

    except FileNotFoundError:
        print(f"File not found: {input_file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


    # Append the formatted latitude and longitude to a file
    with open(output_file_path, 'a') as file:
        file.write(f">>(stationLatitude1): ({user_config['source_latitude']})\n")
        file.write(f">>(stationLongitude1): ({user_config['source_longitude']})\n")
        file.write(f">>(stationLatitude2): ({user_config['destination_latitude']})\n")
        file.write(f">>(stationLongitude2): ({user_config['destination_longitude']})\n")
        file.write(f">>(outputFileName): (HopCountPath.txt)\n")
        file.write(f">>(execute_function): (printStationHopcountPath)\n")
        

    print("\nLatitude and longitude have been appended to the file......................\n")

    
    
    

    # Execute ./sattrack
    try:
        
        print("\nExecuting ./satrrack.......................................................\n")

        # Use subprocess to run the external command
        with open(os.path.join(directory, 'HopCountOutput.txt'), 'w') as output_file:
            subprocess.run(['./sattrack'], cwd=directory, stdout=output_file, stderr=subprocess.STDOUT, check=True)


        # Wait for a short time to ensure execution completes (if needed)
        time.sleep(1)  # Adjust the wait time as necessary

        # Read the output1.txt file
        output_file_path = os.path.join(directory, 'HopCountPath.txt')
        with open(output_file_path, 'r') as file:
            output_data = file.read()
        
        # Display the read content
        # print("Output from output1.txt:")
        # print(output_data)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while executing ./sattrack: {e}")
    except FileNotFoundError:
        print(f"File not found: {output_file_path}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


    print("\nExecuting ./satrrack successfully. Output in HopCountPath.txt..............\n")


    data = load_json(output_file_path)
    
    available_sats_list1 = data.get("availableSatsList1", [])
    available_sats_list2 = data.get("availableSatsList2", [])
    path_list = data.get("pathlist", [])
    
    print("\nAvailable Sats List 1:", available_sats_list1)
    print("Available Sats List 2:", available_sats_list2)
    print("Path List:", path_list)

    deployable_paths = []
    vnf_list = user_config["vnfs"]
    initial_resource = {}

    for path_idx, path in enumerate(path_list, 1):
        print(f"\n{YELLOW}▶ 正在檢查路徑 {path_idx}: {path}{NC}")
        deployment_successful = True
        sat_resource_cache = copy.deepcopy(initial_resource)  # 快取衛星資源狀態
        deployment_map = {}
        used_satellites = set()
        total_resource_used = {"cpu": 0, "mem": 0, "disk": 0}
        last_deployed_sat_index = 0  # 嘗試部署的衛星起始點

        for vnf in vnf_list:
            vnf_deployed = False
            print(f"\n  嘗試部署 VNF：{vnf['vnf_name']}，需求：CPU={vnf['cpu']}, Memory={vnf['memory']}GB, Disk={vnf['storage']}GB")

            # 優先找尚未部署過的衛星
            for sat_index in range(last_deployed_sat_index, len(path)):
                sat_id = path[sat_index]

                # 先從快取取得資源，沒有就查詢後存入快取
                if sat_id not in initial_resource:
                    res_data = query_sat_resource(sat_id)
                    if res_data is None:
                        print(f"{RED}    ⚠ 無法取得衛星 {sat_id} 的資源資料，跳過此衛星{NC}")
                        continue
                    sat_resource_cache[sat_id] = copy.deepcopy(res_data)
                    initial_resource[sat_id] = copy.deepcopy(res_data)


                

                if resource_sufficient(sat_resource_cache,sat_id, vnf):
                    if sat_id not in used_satellites:
                        # 優先使用新衛星
                        pass
                    elif len(used_satellites) < len(path):
                        continue  # 還有其他沒用過的衛星可試

                    deployment_map[vnf["vnf_name"]] = sat_id
                    sat_resource_cache[sat_id]['used_now']['CPU'] += vnf["cpu"]
                    sat_resource_cache[sat_id]['used_now']['Memory_MB'] += vnf["memory"] * 1024
                    sat_resource_cache[sat_id]['used_now']['Disk_GB'] += vnf["storage"]

                    # 累加此 VNF 使用的資源量
                    total_resource_used["cpu"] += vnf["cpu"]
                    total_resource_used["mem"] += vnf["memory"] * 1024
                    total_resource_used["disk"] += vnf["storage"]

                    used_satellites.add(sat_id)
                    vnf_deployed = True
                    last_deployed_sat_index = sat_index
                    print(f"{GREEN}    ✅ 成功部署 {vnf['vnf_name']} 至衛星 {sat_id}{NC}")
                    break
                else:
                    print(f"{RED}    ❌ 衛星 {sat_id} 資源不足，無法部署此 VNF{NC}")

            if not vnf_deployed:
                print(f"{RED}  ✘ 無法為 VNF：{vnf['vnf_name']} 找到合適的衛星，此路徑部署失敗{NC}")
                deployment_successful = False
                break

        if deployment_successful:
            print(f"{GREEN}\n  ✅ 路徑 {path} 可成功部署所有 VNF{NC}")
            deployable_paths.append({
                "path": path,
                "vnf_to_sat": deployment_map,
                "total_resource_used": total_resource_used
            })


    # 顯示所有成功部署的路徑
    if deployable_paths:
        #  加入使用率計算
        def calculate_usage_ratio(plan):
            """
            使用者自訂權重 (CPU/MEM/DISK) 來計算分數
            分數越低越好（代表使用越平均、壓力越低）
            """

            path = plan["path"]
            used_plan = plan["total_resource_used"]
            total = {"cpu": 0, "mem": 0, "disk": 0}
            used_now = {"cpu": 0, "mem": 0, "disk": 0}

            # 只計算真正用上的衛星
            used_sat_ids = set(plan["vnf_to_sat"].values())

            for sat_id in used_sat_ids:
                res = initial_resource.get(sat_id)
                if res:
                    total["cpu"] += res["total"]["CPU"]
                    total["mem"] += res["total"]["Memory_MB"]
                    total["disk"] += res["total"]["Disk_GB"]
                    used_now["cpu"] += res["used_now"]["CPU"]
                    used_now["mem"] += res["used_now"]["Memory_MB"]
                    used_now["disk"] += res["used_now"]["Disk_GB"]

            # 取得三個使用率
            cpu_ratio = (used_plan["cpu"] + used_now["cpu"]) / total["cpu"] if total["cpu"] else 0
            mem_ratio = (used_plan["mem"] + used_now["mem"]) / total["mem"] if total["mem"] else 0
            disk_ratio = (used_plan["disk"] + used_now["disk"]) / total["disk"] if total["disk"] else 0

            # 依照使用者權重計算總分          
            score = (
                cpu_ratio * weights["cpu"] +
                mem_ratio * weights["mem"] +
                disk_ratio * weights["disk"]
            )

            return {
                "score": score,
                "cpu_ratio": cpu_ratio,
                "mem_ratio": mem_ratio,
                "disk_ratio": disk_ratio
            }

        print(f"\n{GREEN}符合條件的路徑與部署方案如下：{NC}")
        for idx, item in enumerate(deployable_paths, 1):
            print(f"\n方案 {idx}:")
            print(f"  Path: {item['path']}")
            for vnf_name, sat_id in item['vnf_to_sat'].items():
                print(f"  - {vnf_name} 部署於衛星 {sat_id}")
            tr = item["total_resource_used"]
            print(f"  ✦ 總資源使用量：CPU={tr['cpu']}, Mem={tr['mem']}MB, Disk={tr['disk']}GB")

            # ➤ 顯示使用率
            ratios = calculate_usage_ratio(item)
            print(f"  ➤ 使用率：CPU={ratios['cpu_ratio']*100:.1f}%, Mem={ratios['mem_ratio']*100:.1f}%, Disk={ratios['disk_ratio']*100:.1f}%")
            print(f"  ➤ 權重後分數（越低越好）：{ratios['score']:.4f}")


        # 根據權重分數（score）選出最佳方案
        best_plan = min(deployable_paths, key=lambda p: calculate_usage_ratio(p)["score"])
        ratios = calculate_usage_ratio(best_plan)

        print(f"\n{YELLOW}最佳部署方案（依資源使用率）為：{NC}")
        print(f"  Path: {best_plan['path']}")
        for vnf_name, sat_id in best_plan['vnf_to_sat'].items():
            print(f"  - {vnf_name} 部署於衛星 {sat_id}")
        tr = best_plan["total_resource_used"]
        print(f"  ✦ 資源使用量：CPU={tr['cpu']}, Mem={tr['mem']}MB, Disk={tr['disk']}GB")
        print(f"  ➤ 使用率：CPU={ratios['cpu_ratio']*100:.1f}%, Mem={ratios['mem_ratio']*100:.1f}%, Disk={ratios['disk_ratio']*100:.1f}%")
        print(f"  ➤ 使用者權重：CPU={weights['cpu']}, MEM={weights['mem']}, DISK={weights['disk']}")
        print(f"  ➤ 權重後分數（越低越好）：{ratios['score']:.4f}")

        # Update selected sat_id in json config
        for vnf in config[ns_name]["vnfs"]:
            vnf_name = vnf["vnf_name"]
            if vnf_name in best_plan["vnf_to_sat"]:
                vnf["sat_id"] = best_plan["vnf_to_sat"][vnf_name]

        # Update path list: [起點, 所有VNF對應sat_id, 終點]
        path_with_vnf = []
        try:
            start_sat = best_plan["path"][0]
            end_sat = best_plan["path"][-1]
            path_with_vnf.append(start_sat)
            for vnf in config[ns_name]["vnfs"]:
                path_with_vnf.append(vnf["sat_id"])
            path_with_vnf.append(end_sat)
            config[ns_name]["path"] = path_with_vnf
            print(f"{GREEN}✔ 已新增 path 欄位: {path_with_vnf}{NC}")
        except Exception as e:
            print(f"{RED}✘ 產生 path 欄位失敗: {e}{NC}")

        # Save the updated config back to the original JSON file 
        script_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(script_dir, '..', 'Operation-VNFs', 'ns_vnf_config.json')

        try:
            with open(json_path, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"{GREEN}\nSuccessfully updated 'sat_id' in ns_vnf_config.json for NS: {ns_name}\n{NC}")
        except Exception as e:
            print(f"{RED}✘ Error writing to ns_vnf_config.json: {e}{NC}")

    else:
        print(f"\n{RED}✘ 沒有符合條件的路徑可以部署所有 VNF{NC}")
    
    

if __name__ == "__main__":
    main()
