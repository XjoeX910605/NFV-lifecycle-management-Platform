#!/bin/bash

# ==========================================
# Nodegenerator V3.0 (抗斷線版)
# ==========================================
KVM_HOST="140.114.77.84"
KVM_USER="wmnet"
CONTROLLER_IP="192.168.100.148"
ROOT_PASS="lab741lab741"
VM_NAME="$1"

if [ -z "$VM_NAME" ]; then
    echo "❌ 錯誤: 請輸入節點名稱 (範例: ./Nodegenerator.sh test05)"
    exit 1
fi

echo "🚀 [Client] 連線到 KVM ($KVM_HOST) 開始作業..."

ssh $KVM_USER@$KVM_HOST "sudo bash -s" << 'REMOTE_SCRIPT' "$VM_NAME" "$CONTROLLER_IP" "$ROOT_PASS"

    NAME="$1"
    CTRL_IP="$2"
    PASS="$3"
    IMG_DIR="/var/lib/libvirt/images"
    TEMPLATE="$IMG_DIR/Openstack_template.qcow2"
    NEW_IMG="$IMG_DIR/${NAME}.qcow2"

    echo "========================================"
    echo "🏗️ [Host] 建立與啟動節點: $NAME"
    echo "========================================"

    # --- 步驟 0-3: 建立 VM (保持不變) ---
    if ! command -v sshpass &> /dev/null; then
        apt-get update && apt-get install -y sshpass
    fi

    if [ ! -f "$NEW_IMG" ]; then
        qemu-img create -f qcow2 -b "$TEMPLATE" -F qcow2 "$NEW_IMG" > /dev/null
    fi

    if ! virsh list --all | grep -q " $NAME "; then
        virt-install --name "$NAME" --memory 8192 --vcpus 4 \
          --disk path="$NEW_IMG",device=disk,bus=virtio \
          --import --noautoconsole --network network=network,model=virtio --network network=network,model=virtio --graphics none
    fi

    echo "⏳ [Host] 等待 IP..."
    VM_IP=""
    while [ -z "$VM_IP" ]; do
        sleep 5
        VM_IP=$(virsh domifaddr "$NAME" | grep ipv4 | awk '{print $4}' | cut -d/ -f1 | head -n1)
    done
    echo "✅ [Host] VM IP: $VM_IP"

    echo "📡 [Host] 等待 SSH..."
    while ! nc -z "$VM_IP" 22; do sleep 3; done
    sleep 10

    # ========================================================
    # 🌟 修改重點：步驟 4 (背景執行 + 監控)
    # ========================================================
    # --- 4.1 環境準備 (同步執行) ---
    echo "⚙️ [Host -> VM] 設定主機名稱與 Hosts..."
    # 這裡加上 -n 是為了保護後面的腳本不被吃掉
    sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$VM_IP \
        "echo '$PASS' | sudo -S hostnamectl set-hostname $NAME && \
         echo '$PASS' | sudo -S sed -i 's/127.0.1.1.*/127.0.1.1 $NAME/g' /etc/hosts"
    
    echo "✅ [Host] 環境設定完成，準備啟動安裝..."
    sleep 2

    # --- 4.2 啟動背景安裝 (非同步執行) ---
    echo "🚀 [Host -> VM] 發送安裝指令 (Fire & Forget)..."
    
    # 這裡加上 -n 且配上 nohup
    sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$VM_IP \
        "nohup /opt/stack/setup_compute.sh > /tmp/stack_install.log 2>&1 < /dev/null & sleep 2"

    echo "⏳ [Host] 指令已發送，進入監控模式..."

    # 2. 迴圈檢查標誌 (檢查 stack.sh 是否跑完)
    # 我們檢查 systemd 的 devstack@n-cpu 服務是否啟動，或是檢查 log 結尾
    start_time=$(date +%s)
    installed=0
    
    while [ $installed -eq 0 ]; do
        sleep 30
        
        # 檢查 Log 檔最後一行是否有成功訊息 (根據你的 Image 輸出)
        # 或者簡單點：檢查 n-cpu 服務是否 Active
        STATUS=$(sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$VM_IP "systemctl is-active devstack@n-cpu 2>/dev/null")
        
        current_time=$(date +%s)
        elapsed=$((current_time - start_time))
        
        if [ "$STATUS" == "active" ]; then
            installed=1
            sleep 20  # 等待服務穩定
            echo -e "\n✅ [Host] 檢測到 Nova CPU 服務已啟動！安裝完成。"

            # === ✨ 新增功能：顯示 Log 最後 40 行 ===
            echo -e "\n📄 [Host] 顯示安裝日誌最後 40 行 (/opt/stack/logs/stack.sh.log)..."
            echo "---------------------------------------------------------------"
            sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$VM_IP "tail -n 40 /opt/stack/logs/stack.sh.log"
            echo "---------------------------------------------------------------"
        else
            # 安裝中：顯示進度
            echo -ne "\033[2K\r    🔄 安裝進行中... 已耗時 ${elapsed} 秒 (服務狀態: $STATUS)"
        fi
        
        if [ $elapsed -gt 2400 ]; then
            echo -e "\n❌ [Host] 安裝超時！顯示目前 Log 結尾供除錯："
            sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$VM_IP "tail -n 40 /opt/stack/logs/stack.sh.log"
            exit 1
        fi
    done

    # ========================================================
    # 🌟 步驟 5 & 6 (現在保證會執行了)
    # ========================================================
    
    # --- 步驟 5: 金鑰同步 ---
    echo -e "\n🔑 [Host] 同步 Migration 金鑰..."
    sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$VM_IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh"
    sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$CTRL_IP "cat ~/.ssh/id_rsa" > /tmp/temp_id_rsa
    sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$CTRL_IP "cat ~/.ssh/authorized_keys" > /tmp/temp_authorized_keys
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no /tmp/temp_id_rsa stack@$VM_IP:~/.ssh/id_rsa
    sshpass -p "$PASS" scp -o StrictHostKeyChecking=no /tmp/temp_authorized_keys stack@$VM_IP:~/.ssh/authorized_keys
    sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$VM_IP "chmod 600 ~/.ssh/id_rsa && chmod 644 ~/.ssh/authorized_keys"
    rm /tmp/temp_id_rsa /tmp/temp_authorized_keys
    echo "✅ [Host] 金鑰同步完成。"

    # --- 步驟 6: Mapping ---
    echo "🗺️ [Host] 通知 Controller 進行 Mapping..."
    sshpass -p "$PASS" ssh -n -o StrictHostKeyChecking=no stack@$CTRL_IP \
        "cd ~/devstack && source openrc admin demo && echo '$PASS' | sudo -S /opt/stack/data/venv/bin/nova-manage cell_v2 discover_hosts --verbose"

    echo "🎉 [Host] 全部流程大功告成！"

REMOTE_SCRIPT

echo "✅ [Client] 腳本結束。"