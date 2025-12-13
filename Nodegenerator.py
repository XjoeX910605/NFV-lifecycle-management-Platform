import paramiko
import time
import socket

# === KVM主機登入資訊（使用密碼） ===
KVM_HOST = "140.114.77.84"
KVM_USER = "wmnet"
KVM_PASS = "lab741lab741"

# === VM帳號密碼（登入使用） ===
VM_USER = "ubuntu"
VM_PASS = "ubuntu"

# === VM設定 ===
VM_NAME = "testvm"
VM_IMAGE_BASE = "/var/lib/libvirt/images/ubuntu-base.qcow2"
VM_IMAGE_NEW = f"/var/lib/libvirt/images/{VM_NAME}.qcow2"

# === 腳本路徑 ===
SCRIPT_LOCAL = "hello.sh"
SCRIPT_REMOTE = f"/home/{VM_USER}/hello.sh"

def ssh_exec_password(ip, username, password, cmd, timeout=5):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password, timeout=timeout)
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    ssh.close()
    return out, err

def sftp_send_file(ip, username, password, local_path, remote_path):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password)
    sftp = ssh.open_sftp()
    sftp.put(local_path, remote_path)
    sftp.chmod(remote_path, 0o755)
    sftp.close()
    ssh.close()

def create_vm_on_kvm():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(KVM_HOST, username=KVM_USER, password=KVM_PASS)

    print("🛠️ 複製 VM 基礎映像")
    ssh.exec_command(f"qemu-img create -f qcow2 -b {VM_IMAGE_BASE} {VM_IMAGE_NEW} 10G")

    print("🚀 執行 virt-install")
    virt_cmd = f"""
    sudo virt-install --name={VM_NAME} \
    --memory=2048 --vcpus=2 \
    --os-variant=ubuntu22.04 \
    --import --disk path={VM_IMAGE_NEW},format=qcow2 \
    --network network=default \
    --graphics none --noautoconsole
    """
    stdin, stdout, stderr = ssh.exec_command(virt_cmd)
    print(stdout.read().decode())
    print(stderr.read().decode())

    print("⏳ 等待開機與分配 IP")
    time.sleep(10)

    ip_cmd = f"sudo virsh domifaddr {VM_NAME} --source agent"
    stdin, stdout, stderr = ssh.exec_command(ip_cmd)
    result = stdout.read().decode()
    ssh.close()

    vm_ip = None
    for line in result.splitlines():
        if "ipv4" in line:
            vm_ip = line.split()[3].split("/")[0]

    if not vm_ip:
        raise RuntimeError("❌ 無法取得 VM IP，請檢查 guest agent 是否啟用")

    print(f"✅ 新 VM IP 為：{vm_ip}")
    return vm_ip

def ssh_to_vm_and_run(ip):
    print("📤 傳送腳本到 VM")
    sftp_send_file(ip, VM_USER, VM_PASS, SCRIPT_LOCAL, SCRIPT_REMOTE)

    print("▶️ 執行腳本")
    out, err = ssh_exec_password(ip, VM_USER, VM_PASS, f"bash {SCRIPT_REMOTE}")
    print("📤 輸出：\n", out)
    if err:
        print("⚠️ 錯誤：\n", err)

if __name__ == "__main__":
    ip = create_vm_on_kvm()
    print("⏳ 等待 VM SSH 可用...")
    for _ in range(10):
        try:
            ssh_exec_password(ip, VM_USER, VM_PASS, "echo VM啟動完成")
            break
        except Exception as e:
            print("等待中...", e)
            time.sleep(5)
    ssh_to_vm_and_run(ip)
