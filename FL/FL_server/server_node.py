import socket
import pickle
import struct
import numpy as np
import time
import sys
import csv
import psutil
import torch
import os

# --- Configuration ---
HOST = '0.0.0.0'
PORT = 5000
ROUNDS = 20
TOTAL_DATASET_SIZE = 50000 # CIFAR-10 training set size

# Get expected client count from command line (Default: 1)
try:
    NUM_CLIENTS = int(sys.argv[1])
except IndexError:
    NUM_CLIENTS = 1

def send_payload(sock, data):
    msg = pickle.dumps(data)
    sock.sendall(struct.pack('>I', len(msg)))
    sock.sendall(msg)

def recv_payload(sock):
    raw_msglen = recvall(sock, 4)
    if not raw_msglen: return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    return pickle.loads(recvall(sock, msglen))

def recvall(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet: return None
        data += packet
    return data

def aggregate_weights(client_weights):
    if not client_weights: return None
    avg_weights = client_weights[0]
    for i in range(1, len(client_weights)):
        for key in avg_weights.keys():
            avg_weights[key] += client_weights[i][key]
    for key in avg_weights.keys():
        avg_weights[key] = torch.div(avg_weights[key], len(client_weights))
    return avg_weights

def main():
    print(f"[Server] Starting FL Server on port {PORT}")
    print(f"[Server] Expected Clients: {NUM_CLIENTS}")
    print(f"[Server] Data Partitioning: Splitting {TOTAL_DATASET_SIZE} images among {NUM_CLIENTS} clients.")
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((HOST, PORT))
    s.listen(NUM_CLIENTS)

    clients = []
    
    # --- 1. Connection & Configuration Phase ---
    # Calculate how many images per client
    split_size = TOTAL_DATASET_SIZE // NUM_CLIENTS
    
    while len(clients) < NUM_CLIENTS:
        conn, addr = s.accept()
        clients.append(conn)
        
        # Assign ID based on arrival order (0, 1, 2...)
        client_id = len(clients) - 1
        
        # Calculate data range for this client
        start_idx = client_id * split_size
        end_idx = start_idx + split_size
        
        # Create a configuration object
        config = {
            'client_id': client_id + 1,  # Human readable ID (1-based)
            'start_idx': start_idx,
            'end_idx': end_idx,
            'num_clients':NUM_CLIENTS
        }
        
        print(f"[Server] Client {client_id+1} connected: {addr}")
        print(f"         Assigning Task: Images {start_idx} to {end_idx}")
        
        # Send configuration to the client immediately
        send_payload(conn, config)

    # --- 2. Training Phase ---
    log_file = f"server_metrics_{NUM_CLIENTS}clients.csv"
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Round", "Total_Traffic_KB", "Agg_Time_Sec", "Server_CPU", "Server_RAM"])

    print("\n[Server] All clients configured. Training Started.")

    for r in range(ROUNDS):
        print(f"\n=== Round {r+1}/{ROUNDS} ===")
        
        client_weights_list = []
        total_size = 0
        start_time = time.time()
        
        # Receive
        for conn in clients:
            try:
                weights = recv_payload(conn)
                if weights:
                    client_weights_list.append(weights)
                    total_size += len(pickle.dumps(weights))/1024
            except Exception as e:
                print(f"[Error] Connection lost: {e}")

        # Aggregate
        if len(client_weights_list) == NUM_CLIENTS:
            global_weights = aggregate_weights(client_weights_list)
            
            # Broadcast
            for conn in clients:
                send_payload(conn, global_weights)
                
            agg_time = time.time() - start_time
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory().percent
            
            print(f"    [Aggregated] Traffic: {total_size:.2f} KB | Time: {agg_time:.4f}s")
            
            with open(log_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([r+1, total_size, agg_time, cpu, ram])
        else:
            print("[Server] Client dropped. Aborting.")
            break
        
        time.sleep(0.5)

    print("\n[Server] FL Completed.")
    for conn in clients: conn.close()
    s.close()

if __name__ == "__main__":
    main()