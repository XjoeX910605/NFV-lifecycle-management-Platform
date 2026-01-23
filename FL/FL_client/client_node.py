import socket
import pickle
import struct
import time
import sys
import os
import urllib.request
import csv
import psutil
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchvision
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Subset # Import Subset
from tqdm import tqdm

# --- Configuration ---
SERVER_PORT = 5000
TOTAL_ROUNDS = 20
BATCH_SIZE = 128
LOCAL_EPOCHS = 2
DATA_DIR = "./cifar10_data"

# NOTE: No Client ID needed in arguments anymore!
if len(sys.argv) < 2:
    print("Usage: python3 client_node.py <SERVER_IP>")
    sys.exit(1)

SERVER_IP = sys.argv[1]

# Global variable to store assigned config
MY_CONFIG = {}

# --- 1. Define Model (VGG-Style) ---
#  ResNet-18 for CIFAR-10  
class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, in_planes, planes, stride=1):
        super(BasicBlock, self).__init__()
        self.conv1 = nn.Conv2d(in_planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(planes)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm2d(planes)

        self.shortcut = nn.Sequential()
        if stride != 1 or in_planes != self.expansion*planes:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_planes, self.expansion*planes, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm2d(self.expansion*planes)
            )

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out += self.shortcut(x)
        out = F.relu(out)
        return out

class ResNetLite(nn.Module):
    def __init__(self, block, num_blocks, num_classes=10):
        super(ResNetLite, self).__init__()
        self.in_planes = 32

        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, stride=1, padding=1, bias=False)
        self.bn1 = nn.BatchNorm2d(32)
        

        self.layer1 = self._make_layer(block, 32, num_blocks[0], stride=1)
        self.layer2 = self._make_layer(block, 64, num_blocks[1], stride=2)
        self.layer3 = self._make_layer(block, 128, num_blocks[2], stride=2)
        self.layer4 = self._make_layer(block, 256, num_blocks[3], stride=2)
        

        self.linear = nn.Linear(256*block.expansion, num_classes)

    def _make_layer(self, block, planes, num_blocks, stride):
        strides = [stride] + [1]*(num_blocks-1)
        layers = []
        for stride in strides:
            layers.append(block(self.in_planes, planes, stride))
            self.in_planes = planes * block.expansion
        return nn.Sequential(*layers)

    def forward(self, x):
        out = F.relu(self.bn1(self.conv1(x)))
        out = self.layer1(out)
        out = self.layer2(out)
        out = self.layer3(out)
        out = self.layer4(out)
        out = F.avg_pool2d(out, 4)
        out = out.view(out.size(0), -1)
        out = self.linear(out)
        return out
        
# --- 2. Data Processing (Dynamic Partitioning) ---
def get_dataloaders():
    # Use config received from server
    start = MY_CONFIG['start_idx']
    end = MY_CONFIG['end_idx']
    cid = MY_CONFIG['client_id']
    
    print(f"[Client {cid}] Loading Dataset Subset: {start} to {end}...")

    transform_train = transforms.Compose([
        transforms.RandomCrop(32, padding=4),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010))
    ])

    transform_test = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.4914, 0.4822, 0.4465), (0.2023, 0.1994, 0.2010))
    ])

    
    # Load full dataset
    full_trainset = torchvision.datasets.CIFAR10(root=DATA_DIR, train=True,
                                            download=True, transform=transform_train) 
    testset = torchvision.datasets.CIFAR10(root=DATA_DIR, train=False,
                                           download=True, transform=transform_test)   


    # Slice the dataset based on Server's instruction
    indices = list(range(start, end))
    my_trainset = Subset(full_trainset, indices)

    trainloader = DataLoader(my_trainset, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    testloader = DataLoader(testset, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)
    
    return trainloader, testloader

# --- 3. Networking ---
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

# --- Main Process ---
def main():
    global MY_CONFIG
    
    print(f"[Client] Connecting to Server {SERVER_IP}...")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    while True:
        try:
            s.connect((SERVER_IP, SERVER_PORT))
            print("[Client] Connected. Waiting for configuration...")
            break
        except:
            time.sleep(3)

    # --- Step 1: Receive Configuration from Server ---
    MY_CONFIG = recv_payload(s)
    print(f"[Client] Configuration Received: {MY_CONFIG}")
    
    client_id = MY_CONFIG['client_id']
    num_clients = MY_CONFIG['num_clients']
    
    log_file = f"client_metrics_{num_clients}_client{client_id}.csv"
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Round", "Global_Test_Accuracy", "Train_Time", "CPU_Usage", "RAM_Usage"])

    # --- Step 2: Prepare Data based on Config ---
    trainloader, testloader = get_dataloaders()
    net = ResNetLite(BasicBlock, [2, 2, 2, 2])
    
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(net.parameters(), lr=0.001)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=TOTAL_ROUNDS)

    # --- Step 3: Training Loop ---
    for r in range(TOTAL_ROUNDS):
        print(f"\n=== Round {r+1}/{TOTAL_ROUNDS} ===")
        
        start_time = time.time()
        net.train()
        
        for epoch in range(LOCAL_EPOCHS):
            with tqdm(trainloader, unit="batch", desc=f"Epoch {epoch+1}/{LOCAL_EPOCHS}") as tepoch:
                for data in tepoch:
                    inputs, labels = data
                    optimizer.zero_grad()
                    outputs = net(inputs)
                    loss = criterion(outputs, labels)
                    loss.backward()
                    optimizer.step()
                    tepoch.set_postfix(loss=loss.item())
            
        train_time = time.time() - start_time
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        scheduler.step()

        # Upload
        print("    Uploading local model...")
        state_dict = {k: v.cpu() for k, v in net.state_dict().items()}
        send_payload(s, state_dict)
        
        # Wait for Global
        print("    Waiting for global model...")
        global_weights = recv_payload(s)
        if global_weights is None: break
        
        # Update
        net.load_state_dict(global_weights)
        print("    Global model loaded.")
        
        # Validation
        net.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for data in tqdm(testloader, desc="Validating", leave=False):
                images, labels = data
                outputs = net(images)
                _, predicted = torch.max(outputs.data, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()
        
        acc = correct / total
        print(f"    Global Acc: {acc:.4f} | Train Time: {train_time:.2f}s | CPU: {cpu}%")

        with open(log_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([r+1, acc, train_time, cpu, ram])
        
    s.close()

if __name__ == "__main__":
    main()