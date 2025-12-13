import json
import os
import subprocess
import sys
import shutil


CONFIG_FILE = "ns_vnf_config.json"


GREEN = '\033[38;5;82m'
NC = '\033[0m'  # No Color

def load_config(ns_name):
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)[ns_name]
    except FileNotFoundError:
        return {}


def create_folder_structure(ns_name, vnfs, base_dir="./OSM_pkg"):
    ns_folder = os.path.join(base_dir, f"{ns_name}_ns")
    os.makedirs(f"{ns_folder}/Files/icons", exist_ok=True)
    os.makedirs(f"{ns_folder}/Licenses", exist_ok=True)
    os.makedirs(f"{ns_folder}/Scripts/charms", exist_ok=True)

    for vnf in vnfs:
        vnf_folder = os.path.join(base_dir, f"{vnf['vnf_name']}_vnf")
        os.makedirs(f"{vnf_folder}/Files/icons", exist_ok=True)
        os.makedirs(f"{vnf_folder}/Files/images", exist_ok=True)
        os.makedirs(f"{vnf_folder}/Licenses", exist_ok=True)
        os.makedirs(f"{vnf_folder}/Scripts/charms", exist_ok=True)
        os.makedirs(f"{vnf_folder}/Scripts/cloud_init", exist_ok=True)
        os.makedirs(f"{vnf_folder}/Scripts/scripts", exist_ok=True)

def generate_nsd_yaml(ns_name, ns_description, vnfs, base_dir="./OSM_pkg"):
    nsd_content = {
        "nsd": {
            "nsd": [
                {
                    "id": f"{ns_name}",
                    "name": f"{ns_name}",
                    "designer": "OSM",
                    "description": ns_description,
                    "version": "1.0",
                    "vnfd-id": [vnf["vnf_name"] for vnf in vnfs],
                    "df": [
                        {
                            "id": "default-df",
                            "vnf-profile": [
                                {
                                    "id": str(i + 1),
                                    "vnfd-id": vnf["vnf_name"],
                                    "virtual-link-connectivity": [
                                        {
                                            "virtual-link-profile-id": f"{ns_name}_nsd_vld0",
                                            "constituent-cpd-id": [
                                                {
                                                    "constituent-base-element-id": str(i + 1),
                                                    "constituent-cpd-id": "vnf-cp0-ext"
                                                }
                                            ]
                                        }
                                    ]
                                }
                                for i, vnf in enumerate(vnfs)
                            ]
                        }
                    ],
                    "virtual-link-desc": [
                        {
                            "id": f"{ns_name}_nsd_vld0",
                            "mgmt-network": True,
                            "vim-network-name": "private"
                        }
                    ]
                }
            ]
        }
    }

    nsd_filename = os.path.join(base_dir, f"{ns_name}_ns/{ns_name}_nsd.yaml")
    with open(nsd_filename, "w") as f:
        import yaml
        yaml.safe_dump(nsd_content, f, sort_keys=False)
    

def generate_vnfd_yaml(vnf, base_dir="./OSM_pkg"):

    image_name = vnf["image"]  # 不含副檔名
    image_filename = f"{image_name}.img"  # 加上副檔名
    image_src = os.path.join("../images", image_filename)
    vnf_folder = os.path.join(base_dir, f"{vnf['vnf_name']}_vnf")
    remote_user = "stack"
    remote_ip = "192.168.100.149"
    remote_image_path = f"/home/{remote_user}/images/{image_filename}"

    if os.path.exists(image_src):
        # 檢查遠端是否已有該映像檔
        check_image_cmd = (
            f"ssh {remote_user}@{remote_ip} "
            f"\". ~/devstack/openrc admin demo && "
            f'openstack image list -f value -c Name | grep -w {image_name}"'
        )
        # print(check_image_cmd)
        result = subprocess.run(check_image_cmd, shell=True, text=True,capture_output=True)
        # print(result)
        if result.returncode == 0 and result.stdout.strip() == image_name:
            print(f"{GREEN}OpenStack 中已存在映像檔：{image_name}，跳過上傳與建立{NC}")
        else:
            print(f"{GREEN}正在上傳映像檔至 {remote_ip}...{NC}")
            scp_cmd = [
                "scp", image_src, f"{remote_user}@{remote_ip}:~/images/"
            ]
            try:
                subprocess.run(scp_cmd, check=True)
                print(f"{GREEN}映像檔 {image_filename} 已上傳至遠端 ~/images/{NC}")

                print(f"{GREEN}正在遠端執行 OpenStack 映像建立...{NC}")
                
                ssh_create_cmd = (
                    f"ssh {remote_user}@{remote_ip} "
                    f"\". ~/devstack/openrc admin demo && "
                    f"openstack image create {image_name} "
                    f"--file ~/images/{image_filename} "
                    f"--disk-format qcow2 --container-format bare --public\""
                )
                subprocess.run(ssh_create_cmd, shell=True, check=True)
                print(f"{GREEN}OpenStack 映像檔 {image_name} 建立完成{NC}")
            except subprocess.CalledProcessError as e:
                print(f"{RED}映像傳送或建立失敗：{e}{NC}")
    else:
        print(f"{RED}找不到映像檔 {image_filename} 於 ../images/，請手動確認{NC}")


    vnfd_content = {
        "vnfd": {
            "id": vnf["vnf_name"],
            "product-name": vnf["vnf_name"],
            "description": "Generated by OSM package generator",
            "provider": "OSM",
            "version": "1.0",
            "mgmt-cp": "vnf-cp0-ext",
            "virtual-storage-desc": [
                {
                    "id": f"{vnf['vnf_name']}-VM-storage",
                    "size-of-storage": vnf["storage"]
                }
            ],
            "virtual-compute-desc": [
                {
                    "id": f"{vnf['vnf_name']}-VM-compute",
                    "virtual-cpu": {
                        "num-virtual-cpu": vnf["cpu"]
                    },
                    "virtual-memory": {
                        "size": vnf["memory"]
                    }
                }
            ],
            "sw-image-desc": [
                {
                    "id": vnf["image"],
                    "name": vnf["image"],
                    "image": vnf["image"]
                }
            ],
            "df": [
                {
                    "id": "default-df",
                    "instantiation-level": [
                        {
                            "id": "default-instantiation-level",
                            "vdu-level": [
                                {
                                    "vdu-id": f"{vnf['vnf_name']}-VM",
                                    "number-of-instances": 1
                                }
                            ]
                        }
                    ],
                    "vdu-profile": [
                        {
                            "id": f"{vnf['vnf_name']}-VM",
                            "min-number-of-instances": vnf["min_vm"],
                            "max-number-of-instances": vnf["max_vm"],
                        }
                    ],
                    "scaling-aspect": [
                        {
                            "id": "manual-scaling_mgmtVM",
                            "aspect-delta-details": {
                                "deltas": [
                                    {
                                        "id": "mgmtVM_manual-scaling",
                                        "vdu-delta": [
                                            {
                                                "id": f"{vnf['vnf_name']}-VM",
                                                "number-of-instances": 1
                                            }
                                        ]
                                    }
                                ]
                            },
                            "name": "manual-scaling_mgmtVM"
                        }
                    ]
                }
            ],
            "vdu": [
                {
                    "id": f"{vnf['vnf_name']}-VM",
                    "name": f"{vnf['vnf_name']}-VM",
                    "description": f"{vnf['vnf_name']}-VM",
                    "sw-image-desc": vnf["image"],
                    "virtual-storage-desc": [
                        f"{vnf['vnf_name']}-VM-storage"
                    ],
                    "virtual-compute-desc": f"{vnf['vnf_name']}-VM-compute",
                    "int-cpd": [
                        {
                            "id": "eth0-int",
                            "virtual-network-interface-requirement": [
                                {
                                    "name": "eth0",
                                    "virtual-interface": {
                                        "type": "PARAVIRT"
                                    }
                                }
                            ]
                        }
                    ]
                    
                }
            ],
            "ext-cpd": [
                {
                    "id": "vnf-cp0-ext",
                    "int-cpd": {
                        "vdu-id": f"{vnf['vnf_name']}-VM",
                        "cpd": "eth0-int"
                    }
                }
            ]
        }
    }

    vnfd_filename = os.path.join(base_dir, f"{vnf['vnf_name']}_vnf/{vnf['vnf_name']}_vnfd.yaml")
    with open(vnfd_filename, "w") as f:
        import yaml
        yaml.safe_dump(vnfd_content, f, sort_keys=False)

def display_tree(folder):
    # Display the directory tree of the specific folder
    subprocess.run(["tree", folder])

def main():

    if len(sys.argv) < 2:
        print(f"{GREEN}請輸入 NS 名稱{NC}")
        return

    
    config = load_config(sys.argv[1])
    ns_name = config["ns_name"]
    ns_description = config["ns_description"]
    vnfs = config["vnfs"]

    # Create the folder structure under the "./OSM_pkg" directory
    base_dir = "./OSM_pkg"
    create_folder_structure(ns_name, vnfs, base_dir)
    generate_nsd_yaml(ns_name, ns_description, vnfs, base_dir)

    for vnf in vnfs:
        generate_vnfd_yaml(vnf, base_dir)

    print(f"\n{GREEN}成功建立 {ns_name}_ns 與 {len(vnfs)} 個 VNF 目錄及檔案{NC}\n\n")

    # Display the NS directory structure
    display_tree(os.path.join(base_dir, f"{ns_name}_ns"))
    
    # Display the directory structure for each VNF
    for vnf in vnfs:
        display_tree(os.path.join(base_dir, f"{vnf['vnf_name']}_vnf"))

if __name__ == "__main__":
    main()
    
