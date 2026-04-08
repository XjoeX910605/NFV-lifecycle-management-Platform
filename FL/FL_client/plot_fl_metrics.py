import pandas as pd
import matplotlib.pyplot as plt
import os

# --- 設定字體與全域樣式 (為了學術論文排版) ---
plt.rcParams.update({
    'font.size': 14,
    'axes.labelsize': 16,
    'axes.titlesize': 18,
    'legend.fontsize': 14,
    'lines.linewidth': 2.5,
    'lines.markersize': 8
})

def plot_accuracy():
    plt.figure(figsize=(8, 6))
    
    # 讀取三個情境的 Client 1 準確度 (與腳本在同一個資料夾)
    files = {
        '1 Client': 'client_metrics_1.csv',
        '2 Clients': 'client_metrics_2_client1.csv',
        '3 Clients': 'client_metrics_3_client1.csv'
    }
    
    markers = ['o', 's', '^']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    for (label, filename), marker, color in zip(files.items(), markers, colors):
        if os.path.exists(filename):
            df = pd.read_csv(filename)
            # 確保欄位名稱正確
            if 'Global_Test_Accuracy' in df.columns:
                plt.plot(df['Round'], df['Global_Test_Accuracy'], marker=marker, color=color, label=label)
            else:
                print(f"Warning: 找不到 Global_Test_Accuracy 欄位 in {filename}")
        else:
            print(f"Warning: 找不到檔案 {filename}")
            
    plt.title('FL Global Model Convergence')
    plt.xlabel('Communication Round')
    plt.ylabel('Test Accuracy')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig('fl_accuracy.pdf', format='pdf', dpi=300)
    print("Saved: fl_accuracy.pdf")
    plt.close()

def plot_traffic():
    plt.figure(figsize=(7, 6))
    
    # 動態讀取 Server 端的 CSV 檔案來計算流量
    # 腳本在 FL_client 下，所以用 ../FL_server/ 返回上一層並進入伺服器資料夾
    files = {
        '1 Client': '../FL_server/server_metrics_1clients.csv',
        '2 Clients': '../FL_server/server_metrics_2clients.csv',
        '3 Clients': '../FL_server/server_metrics_3clients.csv'
    }
    
    scenarios = []
    traffic_mb = []
    
    for label, filepath in files.items():
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            
            # 假設您的流量欄位叫做 'Total_Traffic_KB'
            # 這裡計算 20 輪的「平均流量」，並除以 1024 轉換為 MB
            if 'Total_Traffic_KB' in df.columns:
                avg_traffic_kb = df['Total_Traffic_KB'].mean()
                traffic_mb.append(avg_traffic_kb / 1024)
                scenarios.append(label)
            else:
                print(f"Warning: 找不到 Total_Traffic_KB 欄位 in {filepath}")
        else:
            print(f"Warning: 找不到檔案 {filepath}")
    
    # 如果有成功讀取到資料，就開始畫圖
    if traffic_mb:
        bars = plt.bar(scenarios, traffic_mb, color='#4C72B0', width=0.5, edgecolor='black')
        
        plt.title('Network Traffic Overhead per Round')
        plt.xlabel('Number of FL Clients')
        plt.ylabel('Aggregated Traffic (MB)')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # 在柱狀圖上方標示數值
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f'{yval:.1f} MB', ha='center', va='bottom', fontweight='bold')
            
        # 動態設定 Y 軸上限，預留 20% 的空間給上面的文字，才不會頂到天花板
        plt.ylim(0, max(traffic_mb) * 1.2) 
        plt.tight_layout()
        plt.savefig('fl_traffic.pdf', format='pdf', dpi=300)
        print("Saved: fl_traffic.pdf")
    else:
        print("無法產生流量圖：因為沒有讀到有效的流量資料。")
        
    plt.close()

if __name__ == '__main__':
    plot_accuracy()
    plot_traffic()