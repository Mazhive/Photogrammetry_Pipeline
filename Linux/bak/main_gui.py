import sys
import os
import subprocess
import shutil
import psutil
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QHBoxLayout, QWidget, QFileDialog, QTextEdit, QLabel, 
                             QLineEdit, QProgressBar, QGroupBox)
from PyQt6.QtCore import Qt, QTimer

class PhotogrammetryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Van Voorn Photogrammetry Engine - Portable Root Edition")
        self.resize(1100, 950)

        # --- DYNAMISCHE PAD BEPALING (ROOT) ---
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.is_running = False
        self.init_ui()
        
        # CPU Monitor Timer
        self.cpu_timer = QTimer()
        self.cpu_timer.timeout.connect(self.update_cpu_usage)
        self.cpu_timer.start(1000)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # --- SECTIE 1: CONFIGURATIE (MESHROOM) ---
        config_group = QGroupBox("Meshroom Configuratie")
        config_layout = QVBoxLayout()

        # Meshroom Bin Pad
        bin_layout = QHBoxLayout()
        self.mesh_bin_input = QLineEdit("/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/bin")
        btn_browse_bin = QPushButton("Browse Bin")
        btn_browse_bin.clicked.connect(lambda: self.browse_directory(self.mesh_bin_input))
        bin_layout.addWidget(self.mesh_bin_input)
        bin_layout.addWidget(btn_browse_bin)

        # Meshroom Lib Pad
        lib_layout = QHBoxLayout()
        self.mesh_lib_input = QLineEdit("/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/aliceVision/lib:/mnt/VG_00/Portable.APPS/Meshroom/Meshroom-2025.1.0/lib")
        btn_browse_lib = QPushButton("Browse Lib")
        btn_browse_lib.clicked.connect(lambda: self.browse_directory(self.mesh_lib_input, append=True))
        lib_layout.addWidget(self.mesh_lib_input)
        lib_layout.addWidget(btn_browse_lib)

        config_layout.addWidget(QLabel("Pad naar aliceVision/bin:"))
        config_layout.addLayout(bin_layout)
        config_layout.addWidget(QLabel("Pad naar Libraries (LD_LIBRARY_PATH):"))
        config_layout.addLayout(lib_layout)
        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # --- SECTIE 2: PROJECT INFO ---
        project_group = QGroupBox("Project Instellingen")
        project_layout = QVBoxLayout()

        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("Bijv: Aardbeipot_Scan_01")
        
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Selecteer de map met foto's...")
        btn_browse_photos = QPushButton("Browse Foto's")
        btn_browse_photos.clicked.connect(lambda: self.browse_directory(self.path_input))
        
        photo_layout = QHBoxLayout()
        photo_layout.addWidget(self.path_input)
        photo_layout.addWidget(btn_browse_photos)

        project_layout.addWidget(QLabel("Unieke Projectnaam:"))
        project_layout.addWidget(self.project_name_input)
        project_layout.addWidget(QLabel("Bron Foto Map:"))
        project_layout.addLayout(photo_layout)
        project_group.setLayout(project_layout)
        layout.addWidget(project_group)

        # --- SECTIE 3: STATUS & CPU BALK ---
        status_layout = QHBoxLayout()
        self.status_label = QLabel(f"Root: {self.base_dir}")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        
        # CPU Label en Balk
        cpu_layout = QHBoxLayout()
        cpu_text_label = QLabel("CPU Usage:")
        cpu_text_label.setStyleSheet("font-weight: bold; color: #ccc;")
        
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setFixedWidth(200)
        self.cpu_bar.setTextVisible(True)
        self.cpu_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cpu_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #444;
                border-radius: 3px;
                text-align: center;
                background: #222;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
            }
        """)
        
        cpu_layout.addWidget(cpu_text_label)
        cpu_layout.addWidget(self.cpu_bar)
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addLayout(cpu_layout)
        layout.addLayout(status_layout)

        # --- SECTIE 4: BEDIENING ---
        self.btn_start = QPushButton("🚀 START RECONSTRUCTIE")
        self.btn_start.setStyleSheet("background-color: #1b5e20; color: white; font-weight: bold; padding: 15px; font-size: 14px;")
        self.btn_start.clicked.connect(self.run_full_pipeline)
        
        self.btn_stop = QPushButton("🛑 STOP")
        self.btn_stop.setStyleSheet("background-color: #b71c1c; color: white; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_process)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        layout.addLayout(btn_layout)

        # Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #000; color: #00ff00; font-family: 'Monospace'; font-size: 10pt;")
        layout.addWidget(self.log_output)

    def browse_directory(self, line_edit_widget, append=False):
        folder = QFileDialog.getExistingDirectory(self, "Selecteer Map")
        if folder:
            if append and line_edit_widget.text():
                line_edit_widget.setText(f"{line_edit_widget.text()}:{folder}")
            else:
                line_edit_widget.setText(folder)

    def update_cpu_usage(self):
        usage = psutil.cpu_percent()
        self.cpu_bar.setValue(int(usage))
        # Kleur aanpassen op basis van belasting
        color = "#f44336" if usage > 85 else "#4caf50"
        self.cpu_bar.setStyleSheet(f"""
            QProgressBar::chunk {{ background-color: {color}; }} 
            QProgressBar {{ border: 1px solid #444; text-align: center; background: #222; color: white; }}
        """)

    def log(self, text):
        self.log_output.append(text)
        self.log_output.ensureCursorVisible()
        QApplication.processEvents()

    def stop_process(self):
        subprocess.run("docker stop $(docker ps -q)", shell=True)
        self.log("\n[!] PROCES AFGEBROKEN DOOR GEBRUIKER")

    def run_command(self, cmd, env=None):
        process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=True)
        for line in process.stdout:
            self.log(line.strip())
        process.wait()
        return process.returncode

    def run_full_pipeline(self):
        mesh_bin = self.mesh_bin_input.text().strip()
        mesh_lib = self.mesh_lib_input.text().strip()
        photo_dir = self.path_input.text().strip()
        project_name = self.project_name_input.text().strip()

        if not photo_dir or not project_name:
            self.log("[FOUT] Vul een projectnaam in en selecteer een fotomap.")
            return

        work_dir = os.path.join(self.base_dir, "projects", project_name)
        colmap_dir = os.path.join(work_dir, "colmap_data")

        sfm_file, _ = QFileDialog.getOpenFileName(self, "Selecteer SfM bestand", photo_dir, "*.sfm *.abc")
        if not sfm_file: return

        if os.path.exists(work_dir): shutil.rmtree(work_dir)
        os.makedirs(work_dir, exist_ok=True)

        self.log(f"--- START PROJECT: {project_name} ---")

        # 1. Meshroom Export
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = mesh_lib
        env["ALICEVISION_ROOT"] = os.path.dirname(mesh_bin)
        
        export_cmd = f"'{mesh_bin}/aliceVision_exportColmap' -i '{sfm_file}' -o '{colmap_dir}'"
        if self.run_command(export_cmd, env) != 0:
            self.log("[FOUT] Meshroom export mislukt.")
            return

        # 2. Patching (Pinhole Hack)
        self.log("--- CONFIGUREREN CAMERA MODEL (PINHOLE) ---")
        src_cam = None
        for root, dirs, files in os.walk(colmap_dir):
            if "cameras.txt" in files:
                src_cam = os.path.join(root, "cameras.txt")
                src_images = os.path.join(root, "images.txt")
                src_points = os.path.join(root, "points3D.txt")
                break

        if src_cam:
            dst_sparse = os.path.join(colmap_dir, "sparse")
            os.makedirs(dst_sparse, exist_ok=True)
            with open(src_cam, 'r') as f: lines = f.readlines()
            with open(os.path.join(dst_sparse, "cameras.txt"), 'w') as f:
                for line in lines:
                    if line.startswith("#") or not line.strip(): f.write(line)
                    else:
                        p = line.split()
                        if len(p) >= 8: f.write(f"{p[0]} PINHOLE {p[2]} {p[3]} {p[4]} {p[5]} {p[6]} {p[7]}\n")
            
            shutil.copy(src_images, os.path.join(dst_sparse, "images.txt"))
            shutil.copy(src_points, os.path.join(dst_sparse, "points3D.txt"))
            os.makedirs(os.path.join(colmap_dir, "images"), exist_ok=True)
            subprocess.run(f"cp '{photo_dir}'/*.JPG '{colmap_dir}/images/' 2>/dev/null", shell=True)
            subprocess.run(f"cp '{photo_dir}'/*.jpg '{colmap_dir}/images/' 2>/dev/null", shell=True)
        else:
            self.log("[FOUT] Kon cameras.txt niet vinden.")
            return

        # 3. OpenMVS Docker
        docker_cmd = (
            f"docker run --rm -v '{self.base_dir}':/pipeline ubuntu:24.04 bash -c '"
            f"apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y "
            f"libopencv-dev libjxl-dev libcgal-dev libceres-dev libsuitesparse-dev "
            f"libboost-iostreams-dev libboost-program-options-dev libboost-system-dev "
            f"libboost-serialization-dev libboost-python-dev && "
            f"cd /pipeline/projects/{project_name} && "
            f"/pipeline/bin/InterfaceCOLMAP -i colmap_data -o model.mvs && "
            f"/pipeline/bin/DensifyPointCloud model.mvs --estimate-roi 0 && "
            f"/pipeline/bin/ReconstructMesh model_dense.mvs && "
            f"/pipeline/bin/TextureMesh model_dense.mvs --mesh-file model_dense_mesh.ply --export-type obj"
            "'"
        )

        self.log("--- START OPENMVS DOCKER (REKENFASE) ---")
        if self.run_command(docker_cmd) == 0:
            self.log(f"\n[SUCCES] Project {project_name} afgerond!")
        else:
            self.log("\n[FOUT] Er is iets misgegaan in de Docker fase.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PhotogrammetryApp()
    window.show()
    sys.exit(app.exec())
