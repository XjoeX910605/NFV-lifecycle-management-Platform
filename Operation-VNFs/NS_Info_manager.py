import json

GREEN = '\033[38;5;82m'
YELLOW = '\033[93m'
NC = '\033[0m'  # No Color

CONFIG_FILE = "ns_vnf_config.json"

def input_with_default(prompt, default):
    user_input = input(f"{prompt}（例如：{default}）：")
    return user_input.strip() or default

def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)
    print(f"\n{GREEN}設定已儲存至 {CONFIG_FILE}{NC}")

def display_all_name(config):
    print(f"\n{GREEN}目前已有的 NS 名稱：{NC}")
    for ns_name in config.keys():
        print(f"- {ns_name}")

def display_detail(config, ns_name):
    if ns_name in config:
        print(f"\n{YELLOW}NS：{ns_name}{NC}")
        print(json.dumps(config[ns_name], indent=4))
    else:
        print(f"{YELLOW}找不到 NS {ns_name}{NC}")
    

def collect_ns():
    print(f"\n\n{GREEN}----------- 請輸入 NS 的相關資訊 -----------{NC}\n")
    ns_name = input_with_default("請輸入 NS 名稱", "FL")
    ns_description = input_with_default("請輸入 NS 描述", "Federated Learning NS")

    latitude1 = float(input_with_default("Source Latitude", "24"))
    longitude1 = float(input_with_default("Source Longitude", "151"))
    latitude2 = float(input_with_default("Destination Latitude", "20"))
    longitude2 = float(input_with_default("Destination Longitude", "-151"))

    formatted_latitude1 = format(latitude1, '.5f')
    formatted_longitude1 = format(longitude1, '.5f')
    formatted_latitude2 = format(latitude2, '.5f')
    formatted_longitude2 = format(longitude2, '.5f')

    vnfs = []
    num_vnfs = int(input_with_default("請輸入 VNF 數量", "2"))

    for i in range(num_vnfs):
        print(f"\n{GREEN}--------- 請輸入第 {i+1} 個 VNF 的資訊 ---------{NC}\n")
        vnf = {
            "vnf_name": input_with_default("VNF 名稱", "FL_client"),
            "id" : i + 1,
            "cpu": int(input_with_default("CPU 數量", "2")),
            "memory": int(input_with_default("記憶體大小（GB)", "2")),
            "storage": int(input_with_default("儲存空間大小（GB)", "20")),
            "min_vm": int(input_with_default("最小VM個數", "1")),
            "max_vm": int(input_with_default("最大VM個數", "3")),
            "image": input_with_default("映像檔名稱(請放入images資料夾)", "jammy-server-cloudimg-amd64"),
            "sat_id" : -1
        }
        vnfs.append(vnf)

    return {
        ns_name: {
            "ns_name": ns_name,
            "ns_description": ns_description,
            "source_latitude": formatted_latitude1,
            "source_longitude": formatted_longitude1,
            "destination_latitude": formatted_latitude2,
            "destination_longitude": formatted_longitude2,
            "vnfs": vnfs,
            "path": []
        }
    }

def main():
    config = load_config()

    while True:
        print(f"\n{GREEN}操作選項：{NC}")
        print("1. 顯示所有 NS 名稱")
        print("2. 顯示 NS 詳細資訊")
        print("3. 新增 NS")
        print("4. 刪除 NS")
        print("5. 儲存並離開")
        choice = input("請輸入選項（1-4）：").strip()

        match choice:
            case "1":
                display_all_name(config)
            case "2":
                ns_detail_name = input("請輸入要查看的 NS 名稱：").strip()
                display_detail(config,ns_detail_name)
            case "3":
                new_ns = collect_ns()
                config.update(new_ns)
                print(f"{GREEN}已新增 NS {list(new_ns.keys())[0]}{NC}")
            case "4":
                ns_to_delete = input("請輸入要刪除的 NS 名稱：").strip()
                if ns_to_delete in config:
                    del config[ns_to_delete]
                    print(f"{GREEN}已刪除 NS {ns_to_delete}{NC}")
                else:
                    print(f"{YELLOW}找不到 NS {ns_to_delete}{NC}")
            case "5":
                save_config(config)
                break
            case _:
                print(f"{YELLOW}請輸入有效選項（1~4）{NC}")

if __name__ == "__main__":
    main()
