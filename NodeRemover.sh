#!/bin/bash

# ==========================================
# 1. Client 端設定
# ==========================================
KVM_HOST="140.114.77.84"      # KVM 實體機 IP
KVM_USER="wmnet"                # KVM 實體機使用者
CONTROLLER_IP="192.168.100.148" # OpenStack Controller IP
VM_NAME="$1"                    # 要刪除的節點名稱

# ==========================================
# 2. 本地檢查
# ==========================================
if [ -z "$VM_NAME" ]; then
    echo "❌ 錯誤: 請輸入要刪除的節點名稱"
    exit 1
fi

echo "🚀 [Client] 正在連線到 KVM 主機 ($KVM_HOST) 執行清理作業..."

# ==========================================
# 3. 執行遠端清理 (KVM Host 執行區)
# ==========================================
# 注意: REMOTE_SCRIPT 使用單引號包覆，避免在 Client 端展開變數
ssh $KVM_USER@$KVM_HOST "sudo bash -s" << 'REMOTE_SCRIPT' "$VM_NAME" "$CONTROLLER_IP"

    # --- 接收變數 ---
    NAME="$1"
    CTRL_IP="$2"

    echo "========================================"
    echo "🧹 [Host] 開始移除節點: $NAME"
    echo "========================================"

    # --- 步驟 1: 銷毀實體虛擬機 ---
    echo "🔌 [Host] 正在強制關閉虛擬機: $NAME ..."
    sudo virsh destroy "$NAME" 2>/dev/null

    echo "💾 [Host] 正在刪除虛擬機定義與 .qcow2 硬碟檔案..."
    sudo virsh undefine "$NAME" --remove-all-storage 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "🎉 [Host] 節點 $NAME 已徹底從 KVM 宿主機移除。"
    else
        echo "⚠️ [Host] 警告：KVM 內找不到該 VM (可能已被手動刪除)。"
    fi

    # --- 步驟 2: 在 Controller 上清理 OpenStack 紀錄 ---
    echo "📡 [Host -> Controller] 正在清理 OpenStack 紀錄..."
    
    # 注意: 這裡的 EOF 沒有單引號，以便讓 $NAME 在 Host 端展開傳入
    # 但是! 所有要在 Controller 執行的變數/指令替換，都必須加上反斜線 \$
    sshpass -p 'lab741lab741' ssh -o StrictHostKeyChecking=no stack@$CTRL_IP << EOF
        # 🔑 自動加載你的環境變數與路徑
        export PATH="/opt/stack/data/venv/bin:\$PATH"
        cd ~/devstack
        . openrc admin demo

        echo "🔍 [Controller] 檢查節點 $NAME 的服務..."

        # A. 停止並刪除 Compute 服務
        ID=\$(openstack compute service list --host $NAME --service nova-compute -c ID -f value)
        if [ -n "\$ID" ]; then
            openstack compute service set --disable $NAME nova-compute
            openstack compute service delete \$ID
            echo "✅ 已刪除 Nova Compute 服務紀錄。"
        fi

        # B. 清理 Neutron Agents (新增步驟)
        # 通常 Compute Node 會有 OVN Controller agent 或 OVS agent
        AGENT_IDS=\$(openstack network agent list --host $NAME -c ID -f value)
        for AGENT_ID in \$AGENT_IDS; do
            openstack network agent delete \$AGENT_ID
            echo "✅ 已刪除 Neutron Agent: \$AGENT_ID"
        done

        # C. 清理 Placement 資源 (自動解鎖 409 衝突)
        RP_UUID=\$(openstack resource provider list --name $NAME -c uuid -f value)
        if [ -n "\$RP_UUID" ]; then
            echo "🔄 偵測到資源分配，正在強制釋放..."
            
            # 找出所有佔用該 RP 的 Consumer 並刪除紀錄
            # 注意: grep 邏輯可能需要根據 openstack 版本微調，但這裡保持你的邏輯
            CONSUMERS=\$(openstack resource provider show --allocations \$RP_UUID -c allocations -f value | grep -oE "[a-f0-9-]{36}")
            for CONSUMER in \$CONSUMERS; do
                # 某些情況下 Consumer 就是 RP 隨機生成的 UUID，有時是 Instance UUID
                openstack resource provider allocation delete \$CONSUMER || true
                echo "✅ 已嘗試釋放 Consumer: \$CONSUMER"
            done

            # 最後刪除 RP
            openstack resource provider delete \$RP_UUID
            echo "✅ 已從 Placement 完全移除 $NAME。"
        else
            echo "ℹ️ Placement 中已無該節點紀錄。"
        fi
        
        # D. 清理 OVN Chassis (確保 ovn-sbctl 乾淨)
        # 修正: 加上 \$ 讓指令在 Controller 上執行
        CHASSIS_ID=\$(sudo ovn-sbctl --bare --columns=_uuid find chassis hostname=$NAME)
        if [ -n "\$CHASSIS_ID" ]; then
            echo "🧹 偵測到 OVN Chassis，正在移除..."
            sudo ovn-sbctl chassis-del \$CHASSIS_ID
            echo "✅ 已刪除 OVN Chassis 紀錄。"
        fi
EOF

    

REMOTE_SCRIPT

# ==========================================
# 4. 結果回報
# ==========================================
if [ $? -eq 0 ]; then
    echo "✅ [Client] 成功！節點 $VM_NAME 已完全抹除。"
else
    echo "⚠️ [Client] 移除過程中發生異常。"
fi