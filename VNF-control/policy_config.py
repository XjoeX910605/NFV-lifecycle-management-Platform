# -*- coding: utf-8 -*-
"""
policy_config.py
VNF Placement / Migration 的參數設定檔

"""

# ===================== Placement 相關參數 =====================

PLACEMENT_PARAMS = {
    # 使用者自訂資源權重（總和建議 = 1.0）
    # 若只想看 CPU，就設 cpu=1.0, mem=0.0, disk=0.0
    "weights": {
        "cpu": 0.33,   # CPU 使用率權重
        "mem": 0.33,   # Memory 使用率權重
        "disk": 0.34,  # Disk 使用率權重
    },
    # 使用率限制
    "limit": {
        "cpu": 0.9,     # CPU 最高只能使用 90%
        "mem": 0.9,
        "disk": 0.9
    }
}

# ===================== Migration 相關參數 =====================

MIGRATION_PARAMS = {
    "rounds": 100,        # 模擬輪數
    "round_length": 6,    # 每輪相隔秒數
    "k_paths": 5,         # 每輪最多取幾條 simple paths
    "output_round": True,  # 是否每輪印 log
    # 使用者自訂資源權重（總和建議 = 1.0）
    # 若只想看 CPU，就設 cpu=1.0, mem=0.0, disk=0.0
    "weights": {
        "cpu": 0.33,   # CPU 使用率權重
        "mem": 0.33,   # Memory 使用率權重
        "disk": 0.34,  # Disk 使用率權重
    },
    # 使用率限制
    "limit": {
        "cpu": 0.9,     # CPU 最高只能使用 90%
        "mem": 0.9,
        "disk": 0.9
    }
}
