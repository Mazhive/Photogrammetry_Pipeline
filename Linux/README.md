## Van Voorn Photogrammetry Pipeline

<img width="1150" height="977" alt="Screenshot_20260428_105825" src="https://github.com/user-attachments/assets/484238fa-168b-47ba-8335-5c43a2106e52" />

## Van Voorn Photogrammetry Pipeline
A powerful, automated photogrammetry engine designed to bridge the gap between AliceVision and OpenMVS. This tool is optimized for Linux environments (specifically Ubuntu 24.04) and utilizes Docker for maximum stability and library isolation.

## 🚀 Overview
This pipeline automates the process of converting 2D images into a fully textured 3D model (.obj). It specifically addresses "Library Hell" by allowing AliceVision (running Boost 1.86/OpenCV 4.12) and OpenMVS (running Boost 1.83/OpenCV 4.6) to coexist without conflicts through specialized container routing.

## Key Features:
One-Click Docker Setup: No manual terminal commands needed for Docker; the engine can be built directly through the GUI.

Smart Library Isolation: Automatic detection and isolation of conflicting OpenCV versions to prevent "symbol lookup" errors.

Blender Ready: Automatically exports a textured .obj file with associated .mtl and image textures.

Live Monitoring: Real-time log output and CPU load monitoring, optimized for 16-core Ryzen systems.

## 🛠️ Installation & Setup
1. Prerequisites
Before running the script, ensure your system has the necessary dependencies installed. Run the following commands in your terminal:

System Dependencies:

Bash
sudo apt update
sudo apt install -y python3-pyqt6 python3-psutil docker.io
Docker Permissions (Crucial):
To run Docker without sudo (required for the script to manage containers), add your user to the docker group:

Bash
sudo usermod -aG docker $USER
newgrp docker
Hardware Requirements:

Hardware: NVIDIA GPU (for CUDA) or AMD GPU (running in CPU/Force mode).

Storage: High-capacity drive recommended .




Plaintext
/Linux

├── bin/   # AliceVision executable binaries

├── projects/          # Scan output and working directories , you can find the calculated  mtl and obj file here.

├── premade.dockercontainer/          # **** see option B

├── template/                      # Meshroom template you can use in meshroom all nesecary nodes are included

└── main_gui.EN.Final.py        # The Python GUI script

📖 Usage

## Launch the GUI from your terminal:

Bash
python3 main_gui.EN.final.py
Build Engine: Use the "Build Optimized Engine" button within the GUI. The script will automatically generate the Dockerfile and build the container for you.

Scan Project: Select the root folder of your Meshroom cache.

Select SfM: Choose the most recent SfM or Camera file from the dropdown.

Run Pipeline: The tool automatically processes all steps: Export, Patching, Interface, Densify, Reconstruct, and Texture.

Blender: Upon completion, a popup will appear. Click "Open" to navigate directly to your .obj file for import into Blender.

## 📖 Usage
Launch the GUI from your terminal:

Bash
python3 main_gui.EN.final.py
Engine Setup:

   Option A: Use the "Build Optimized Engine" button. The script will automatically generate the Dockerfile and build the container.

**** Option B: If the script detects a premade container in the premade.dockercontainer/ folder (link provided in the file), it will offer to import it automatically.


## ⚠️ Troubleshooting
Resource Busy / Command Not Found: If you try to run the script without the python3 prefix, Linux may mistake it for a Bash script. Always launch with python3.

Disk Space: Photogrammetry generates massive amounts of data. It is highly recommended to use a drive with enough storage space.

Created by   Mazhive - 2026
